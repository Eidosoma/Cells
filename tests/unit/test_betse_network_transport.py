"""Native generated-source correspondence, owner accounting and bounded CPU JAX."""

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_network_transport as transport
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R
from validation.transport import betse_network_transport_reference as reference
from validation.transport.betse_network_transport_fixtures import (
    SPECIES,
    VALENCE,
    cases,
    configuration,
    source_failures,
)

CASES = cases()
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/transport/betse_network_transport_protocol.json").read_text()
)


def evidence(name, payload):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / ("betse-network-" + name + ".json")).write_text(
            json.dumps(payload, indent=2, allow_nan=False) + "\n"
        )


def prepared(row=None, *, capacity=1):
    row = deepcopy(CASES[0] if row is None else row)
    t, p = transport.bind(
        [row["config"]],
        SPECIES,
        VALENCE,
        [0],
        [1],
        [True, True, False],
        area_m2=row["area_m2"],
        temperature_K=row["temperature_K"],
        route_capacity=capacity,
    )
    c = np.array([[row["inside_mM"][s], row["outside_mM"][s], 0.0] for s in SPECIES])
    v, opening, rho = (np.zeros(capacity) for _ in range(3))
    v[0], opening[0], rho[0] = row["voltage_V"], row["availability"], row["rho"]
    return row, c, v, t, p, opening, rho


@pytest.mark.parametrize("row", CASES, ids=[r["name"] for r in CASES])
def test_decimal_source_law_and_conservative_owners(row):
    row, c, v, t, p, a, rho = prepared(row)
    assert transport.LAW_ID == PROTOCOL["law_id"]
    assert transport.domain_valid(c, v, t, p, a, rho, xp=np)
    actual = transport.rates(c, v, t, p, a, rho, xp=np)
    expected = reference.evaluate(
        row["config"],
        row["inside_mM"],
        row["outside_mM"],
        dict(zip(SPECIES, VALENCE, strict=True)),
        **{
            key: row[key]
            for key in ("voltage_V", "temperature_K", "area_m2", "availability", "rho")
        },
    )
    record = dict(
        input=row,
        rates={k: np.asarray(v).tolist() for k, v in actual._asdict().items()},
        expected=expected,
    )
    evidence(row["name"], record)
    for key, value in actual._asdict().items():
        tolerance_key = (
            "energy_atol_J_mol"
            if key.endswith("J_mol")
            else "extent_atol_fmol_s"
            if key == "extent_fmol_s"
            else "current_atol_A_m2"
            if key.endswith("A_m2")
            else "charge_atol_C"
            if key == "outward_current_C_s"
            else "density_atol_mol_m2_s"
            if key == "flux_density_mol_m2_s"
            else "dimensionless_atol"
        )
        atol = PROTOCOL["tolerances"][tolerance_key]
        np.testing.assert_allclose(value[0], expected[key], rtol=5e-12, atol=atol)
    owners = transport.exchange_rates(actual.extent_fmol_s, t, xp=np)
    wanted = np.array([expected["amount_fmol_s"][s] + [0.0] for s in SPECIES])
    np.testing.assert_allclose(owners, wanted, atol=2e-12, rtol=5e-12)
    charge = CHARGE_PER_FMOL * np.asarray(VALENCE) @ owners
    np.testing.assert_allclose(
        charge[:2],
        [-actual.outward_current_C_s[0], actual.outward_current_C_s[0]],
        atol=3e-22,
        rtol=5e-12,
    )
    assert charge[2] == 0


@pytest.mark.parametrize("name", [r["name"] for r in CASES])
def test_authenticated_native_capture_matches_component(name):
    directory = os.environ.get("CELLS_BETSE_NETWORK_NATIVE_CAPTURE")
    if not directory:
        pytest.skip("Bounded runner supplies authenticated native captures")
    captured = json.loads((Path(directory) / (name + ".json")).read_text())
    row, c, v, t, p, a, rho = prepared(captured["input"])
    actual = transport.rates(c, v, t, p, a, rho, xp=np)
    assert captured["status"] == "passed" and not captured["native_geometry_or_updates_executed"]
    np.testing.assert_allclose(
        actual.flux_density_mol_m2_s[0], captured["actual_flux_mol_m2_s"], rtol=5e-12, atol=1e-18
    )
    np.testing.assert_allclose(actual.native_net_z[0], captured["native_net_z"], rtol=0, atol=3e-13)


def test_native_manifest_authenticates_source_and_preserves_known_failures():
    directory = os.environ.get("CELLS_BETSE_NETWORK_NATIVE_CAPTURE")
    if not directory:
        pytest.skip("Bounded runner supplies authenticated native captures")
    root = Path(directory)
    manifest = json.loads((root / "source-manifest.json").read_text())
    source = PROTOCOL["native_source"]
    assert manifest["status"] == "passed" and not manifest["native_simulation"]
    assert manifest["revision"] == source["revision"] and manifest["version"] == source["version"]
    for relative, expected in source["source_sha256"].items():
        assert manifest["files"][relative]["sha256"] == expected
        assert hashlib.sha256((root / "upstream" / relative).read_bytes()).hexdigest() == expected
    assert manifest["successful_cases"] == len(CASES)
    assert manifest["expected_native_failures"] == len(source_failures())
    for name in source_failures():
        assert (
            json.loads((root / (name + ".json")).read_text())["status"] == "expected_native_failure"
        )


def test_literal_q_conversion_is_outside_power_and_product_km_is_absent():
    row = next(row for row in CASES if row["name"] == "literal-q-power-conversion")
    _, c, v, t, p, a, rho = prepared(row)
    result = transport.rates(c, v, t, p, a, rho, xp=np)
    literal = row["inside_mM"]["B"] / row["outside_mM"]["A"] ** 2
    np.testing.assert_allclose(result.log_source_quotient[0], np.log(literal), rtol=0, atol=2e-14)
    corrected = 1000 * literal
    assert abs(result.log_source_quotient[0] - np.log(corrected)) > 6
    changed = deepcopy(row)
    changed["config"]["Km products"] = [1e100]
    _, c2, v2, t2, p2, a2, rho2 = prepared(changed)
    for actual, expected in zip(
        transport.rates(c2, v2, t2, p2, a2, rho2, xp=np), result, strict=True
    ):
        np.testing.assert_array_equal(actual, expected)


def test_irreversible_voltage_and_ignored_regulator_zone_star_semantics():
    row = next(r for r in CASES if r["name"] == "regulation-star-and-env-zone-ignored")
    _, c, v, t, p, a, rho = prepared(row)
    actual = transport.rates(c, v, t, p, a, rho, xp=np)
    changed = deepcopy(row)
    changed["config"]["transporter activators"] = ["Act"]
    changed["config"]["transporter inhibitors"] = ["Aux"]
    changed["config"]["activator zone"] = ["cell"]
    changed["config"]["inhibitor zone"] = ["cell"]
    _, c2, v2, t2, p2, a2, rho2 = prepared(changed)
    np.testing.assert_array_equal(
        transport.rates(c2, v2, t2, p2, a2, rho2, xp=np).regulation, actual.regulation
    )
    irreversible = p._replace(reversible=np.array([False]), standard_free_energy_J_mol=np.zeros(1))
    left = transport.rates(c, np.array([-0.12]), t, irreversible, a, rho, xp=np)
    right = transport.rates(c, np.array([0.06]), t, irreversible, a, rho, xp=np)
    np.testing.assert_array_equal(left.flux_density_mol_m2_s, right.flux_density_mol_m2_s)
    assert left.source_reaction_energy_J_mol[0] == right.source_reaction_energy_J_mol[0] == 0
    negative = next(r for r in CASES if r["name"] == "regulation-direct-inhibitor")
    _, c, v, t, p, a, rho = prepared(negative)
    assert transport.domain_valid(c, v, t, p, a, rho, xp=np)
    assert transport.rates(c, v, t, p, a, rho, xp=np).regulation[0] < 0


def test_padding_shared_destinations_and_integrated_material_ledgers():
    row, c, v, t, p, a, rho = prepared(capacity=3)
    rates = transport.rates(c, v, t, p, a, rho, xp=np)
    for value in rates:
        np.testing.assert_array_equal(value[1:], 0)
    configs = [
        configuration(("Na",)),
        configuration(("Na", "K"), (1, 1), inward=("Na",), outward=("K",)),
    ]
    configs[1]["name"] = "antiport"
    topology, _ = transport.bind(
        configs, SPECIES, VALENCE, [0, 0], [1, 1], [True, True, False], area_m2=4e-10
    )
    extent = np.array([0.01, -0.02])
    expected = np.zeros_like(c)
    expected[SPECIES.index("Na"), :2] = [-0.01, 0.01]
    expected[SPECIES.index("K"), :2] = [0.02, -0.02]
    update = transport.exchange_rates(extent, topology, xp=np)
    np.testing.assert_allclose(update, expected, atol=2e-17, rtol=0)
    balances = transport.material_balances(c, c + update, extent, topology, xp=np)
    for key, value in balances._asdict().items():
        atol = PROTOCOL["tolerances"][
            "charge_atol_C" if key.endswith("_C") else "material_atol_fmol"
        ]
        np.testing.assert_allclose(value, 0, atol=atol, rtol=0)
    corrupted = c + update
    corrupted[0, 0] += 1e-4
    assert (
        np.max(
            np.abs(
                transport.material_balances(
                    c, corrupted, extent, topology, xp=np
                ).amount_residual_fmol
            )
        )
        > 1e-5
    )


@pytest.mark.parametrize(
    "fault",
    [
        "zero",
        "negative",
        "nan",
        "infinite",
        "negative_other",
        "pad_concentration",
        "pad_voltage",
        "pad_opening",
        "pad_rho",
        "temperature",
        "area",
        "maximum",
        "standard",
        "rho",
        "opening",
    ],
)
def test_invalid_trial_rejects_even_when_blocked(fault):
    _, c, v, t, p, a, rho = prepared(
        next(r for r in CASES if r["name"] == "electrogenic-import-0.0"), capacity=2
    )
    a[0] = 0.0
    if fault in ("zero", "negative", "nan", "infinite"):
        c[0, 1] = {"zero": 0.0, "negative": -1.0, "nan": np.nan, "infinite": np.inf}[fault]
    elif fault == "negative_other":
        c[-1, 0] = -1.0
    elif fault == "pad_concentration":
        c[0, 2] = 1e-30
    elif fault in ("pad_voltage", "pad_opening", "pad_rho"):
        {"pad_voltage": v, "pad_opening": a, "pad_rho": rho}[fault][1] = 1e-30
    elif fault in ("temperature", "area", "maximum", "standard"):
        key = {
            "temperature": "temperature_K",
            "area": "area_m2",
            "maximum": "max_flux_mol_m2_s",
            "standard": "standard_free_energy_J_mol",
        }[fault]
        values = np.array(getattr(p, key), copy=True)
        values.flat[0] = np.nan if fault == "standard" else -1.0
        p = p._replace(**{key: values})
    elif fault == "rho":
        rho[0] = -1.0
    else:
        a[0] = 1.1
    with np.errstate(all="ignore"):
        assert not transport.domain_valid(c, v, t, p, a, rho, xp=np)


@pytest.mark.parametrize(
    "fault",
    [
        "zone",
        "duplicate_substrate",
        "missing_km",
        "bad_transfer",
        "negative_multiplier",
        "boolean_rate",
        "nan_energy",
        "charge",
        "negative_km",
        "negative_area",
        "capacity",
        "unknown_key",
    ],
)
def test_strict_native_binding_contract(fault):
    config = configuration()
    kwargs = dict(area_m2=4e-10)
    if fault == "zone":
        config["reaction zone"] = "mit"
    elif fault == "duplicate_substrate":
        config["reactants"] = ["Na", "Na"]
    elif fault == "missing_km":
        config["Km reactants"] = []
    elif fault == "bad_transfer":
        config["transfered into cell"] = ["K"]
    elif fault == "negative_multiplier":
        config["reactant multipliers"] = [-1]
    elif fault == "boolean_rate":
        config["max rate"] = True
    elif fault == "nan_energy":
        config["standard free energy"] = np.nan
    elif fault == "charge":
        config["product multipliers"] = [2]
    elif fault == "negative_km":
        config["Km products"] = [-1]
    elif fault == "negative_area":
        kwargs["area_m2"] = -1
    elif fault == "capacity":
        kwargs["route_capacity"] = 0
    else:
        config["implicit_atp_cost"] = 1
    with pytest.raises(ValueError):
        transport.bind([config], SPECIES, VALENCE, [0], [1], [True, True], **kwargs)


@pytest.mark.parametrize("name", tuple(source_failures()))
def test_native_malformed_source_configurations_reject(name):
    with pytest.raises(ValueError):
        transport.bind(
            [source_failures()[name]], SPECIES, VALENCE, [0], [1], [True, True], area_m2=1e-12
        )


def test_empty_routes_and_blocked_zero_regulator_preserve_domains():
    t, p = transport.bind([], SPECIES, VALENCE, [], [], [True, True], area_m2=0.0)
    c = np.ones((len(SPECIES), 2))
    assert transport.domain_valid(c, np.empty(0), t, p, xp=np)
    result = transport.rates(c, np.empty(0), t, p, xp=np)
    assert all(value.shape == (0,) for value in result)
    np.testing.assert_array_equal(transport.exchange_rates(np.empty(0), t, xp=np), 0)
    for bad in (np.nan, -1.0):
        assert not transport.domain_valid(c, np.empty(0), t, p._replace(temperature_K=bad), xp=np)
    row = next(r for r in CASES if r["name"] == "zero-activator")
    _, c, v, t, p, a, rho = prepared(row)
    assert transport.domain_valid(c, v, t, p, a, rho, xp=np)
    assert transport.rates(c, v, t, p, a, rho, xp=np).flux_density_mol_m2_s[0] == 0


def test_nonrepresentable_finite_rates_and_malformed_axes_reject():
    row = next(r for r in CASES if r["name"] == "electrogenic-import-0.0")
    _, c, v, t, p, a, rho = prepared(row)
    with np.errstate(all="ignore"):
        assert not transport.domain_valid(c, np.array([20.0]), t, p, a, rho, xp=np)
    assert not transport.domain_valid(c, v, t, p._replace(temperature_K=np.ones(2)), a, rho, xp=np)
    assert not transport.domain_valid(c[:-1], v, t, p, a, rho, xp=np)
    assert not transport.domain_valid(c, v, t, p._replace(area_m2=True), a, rho, xp=np)
    evidence(
        "nonrepresentable-rate",
        dict(finite_voltage_V=20.0, expected_rejection=True, floor_or_clipping=False),
    )


@pytest.mark.parametrize("fault", ["maximum", "area", "temperature", "rho", "availability"])
def test_empty_routes_do_not_hide_invalid_raw_parameters(fault):
    t, p = transport.bind([], SPECIES, VALENCE, [], [], [True, True], area_m2=0.0)
    c, opening, rho = np.ones((len(SPECIES), 2)), 1.0, 1.0
    if fault == "maximum":
        p = p._replace(max_flux_mol_m2_s=-1.0)
    elif fault == "area":
        p = p._replace(area_m2=np.inf)
    elif fault == "temperature":
        p = p._replace(temperature_K=0.0)
    elif fault == "rho":
        rho = np.nan
    else:
        opening = -0.1
    assert not transport.domain_valid(c, np.empty(0), t, p, opening, rho, xp=np)
    if fault in ("maximum", "area", "temperature"):
        with pytest.raises(ValueError):
            transport.validate_parameters(p, t)


def test_jax_cpu_compiled_batch_and_shared_owner_scatter():
    import jax
    import jax.numpy as jnp

    _, c, _, _, _, _, _ = prepared()
    rows = [deepcopy(CASES[0])]
    rows.extend(
        deepcopy(next(r for r in CASES if r["name"] == name))
        for name in ("regulation-mixed-direct-sum", "regulation-independent-only")
    )
    for i, row in enumerate(rows):
        row["config"]["name"] = "route-" + str(i)
    t, p = transport.bind(
        [row["config"] for row in rows],
        SPECIES,
        VALENCE,
        [0, 0, 0],
        [1, 1, 1],
        [True, True, False],
        area_m2=4e-10,
        route_capacity=4,
    )
    v = np.array([-0.07, -0.07, -0.07, 0.0])
    a, rho = np.array([0.7, 0.6, 0.8, 0.0]), np.array([0.8, 0.9, 1.2, 0.0])
    cb = np.stack([c, c * 1.1, c * 0.9])
    vb, ab, rb = (np.broadcast_to(x, (3, 4)) for x in (v, a, rho))
    pb = p._replace(temperature_K=np.array([[280.0], [298.15], [320.0]]))
    compiled = jax.jit(
        lambda c, v, p, a, r: (
            transport.rates(c, v, t, p, a, r, xp=jnp),
            transport.domain_valid(c, v, t, p, a, r, xp=jnp),
        )
    )
    actual, valid = compiled(cb, vb, pb, ab, rb)
    evidence(
        "jax-batch",
        dict(
            concentration_mM=cb.tolist(),
            voltage_V=vb.tolist(),
            availability=ab.tolist(),
            rho=rb.tolist(),
            temperature_K=pb.temperature_K.tolist(),
            valid=bool(valid),
            rates={key: np.asarray(value).tolist() for key, value in actual._asdict().items()},
            backend_devices=[device.platform for device in jax.devices()],
        ),
    )
    assert bool(valid) and all(device.platform == "cpu" for device in jax.devices())
    for got, expected in zip(actual, transport.rates(cb, vb, t, pb, ab, rb, xp=np), strict=True):
        np.testing.assert_allclose(got, expected, atol=2e-12, rtol=5e-12)
    scatter = jax.jit(lambda x: transport.exchange_rates(x, t, xp=jnp))
    np.testing.assert_allclose(
        scatter(actual.extent_fmol_s),
        transport.exchange_rates(np.asarray(actual.extent_fmol_s), t, xp=np),
        atol=2e-12,
        rtol=5e-12,
    )


def test_jax_vmap_invalid_world_isolation():
    import jax
    import jax.numpy as jnp

    _, c, v, t, p, a, rho = prepared()
    states = np.stack([c, c, c])
    states[0, SPECIES.index("K"), 1] = 0.0
    checked = jax.jit(jax.vmap(lambda x: transport.domain_valid(x, v, t, p, a, rho, xp=jnp)))
    np.testing.assert_array_equal(checked(states), [False, True, True])
    solved = jax.jit(jax.vmap(lambda x: transport.rates(x, v, t, p, a, rho, xp=jnp).extent_fmol_s))
    values = np.asarray(solved(states))
    evidence(
        "jax-isolation",
        dict(
            concentration_mM=states.tolist(),
            valid=np.asarray(checked(states)).tolist(),
            valid_world_rates=values[1:].tolist(),
            invalid_world_was_rejected=True,
        ),
    )
    np.testing.assert_array_equal(values[1], values[2])
    np.testing.assert_allclose(
        values[1],
        transport.rates(c, v, t, p, a, rho, xp=np).extent_fmol_s,
        atol=2e-12,
        rtol=5e-12,
    )


def test_jax_differentiable_stall_has_native_voltage_slope():
    import jax
    import jax.numpy as jnp

    row = next(r for r in CASES if r["name"] == "electrogenic-import-0.0")
    row = deepcopy(row)
    row["inside_mM"]["Na"] = row["outside_mM"]["Na"] = 10.0
    _, c, _, t, p, a, rho = prepared(row)
    derivative = jax.jit(
        jax.grad(
            lambda v: transport.rates(
                c, jnp.array([v]), t, p, a, rho, xp=jnp
            ).flux_density_mol_m2_s[0]
        )
    )(0.0)
    loading = 10 / row["config"]["Km reactants"][0]
    expected = (
        -row["config"]["max rate"]
        * row["availability"]
        * row["rho"]
        * loading
        / (1 + loading)
        * F
        / (R * row["temperature_K"])
    )
    np.testing.assert_allclose(derivative, expected, atol=1e-15, rtol=5e-12)
    evidence("jax-stall-gradient", dict(actual=float(derivative), expected=expected))


def test_jax_empty_route_kernel_and_raw_parameter_rejection():
    import jax
    import jax.numpy as jnp

    t, p = transport.bind([], SPECIES, VALENCE, [], [], [True, True], area_m2=0.0)
    c = np.ones((len(SPECIES), 2))
    fn = jax.jit(
        lambda temp: (
            transport.rates(c, jnp.empty(0), t, p._replace(temperature_K=temp), xp=jnp),
            transport.domain_valid(c, jnp.empty(0), t, p._replace(temperature_K=temp), xp=jnp),
        )
    )
    actual, valid = fn(298.15)
    assert bool(valid) and all(value.shape == (0,) for value in actual)
    assert not bool(fn(jnp.nan)[1])
    evidence("jax-empty", dict(valid_empty=bool(valid), nan_temperature_rejected=True))
