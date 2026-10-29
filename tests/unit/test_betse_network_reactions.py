"""Native reaction/growth correspondence, explicit accounting and CPU JAX."""

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_network_reactions as chemistry
from validation.chemistry import betse_network_reactions_reference as reference
from validation.chemistry.betse_network_reactions_fixtures import (
    SPECIES,
    base,
    cases,
    limitations,
    molecule,
    reaction,
)

CASES = cases()
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/chemistry/betse_network_reactions_protocol.json").read_text()
)
TOL = PROTOCOL["tolerances"]


def evidence(name, data):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / ("betse-network-reactions-" + name + ".json")).write_text(
            json.dumps(data, indent=2, allow_nan=False) + "\n"
        )


def captured(name):
    if not (directory := os.environ.get("CELLS_BETSE_REACTIONS_NATIVE_CAPTURE")):
        pytest.skip("Bounded wrapper supplies authenticated native reaction captures")
    return json.loads((Path(directory) / (name + ".json")).read_text())


def prepare(raw=None, *, padding=0, compartment_padding=0):
    raw = deepcopy(base() if raw is None else raw)
    c = np.pad(np.asarray(raw["concentration_mM"], float), ((0, 0), (0, compartment_padding)))
    volume = np.pad(np.asarray(raw["volume_m3"], float), (0, compartment_padding))
    args = dict(
        cell_to_environment={int(k): int(v) for k, v in raw["cell_to_environment"].items()},
        growth_targets=raw["growth_targets"],
        growth_modulation=raw["growth_modulation"],
        time_dilation=raw["time_dilation"],
        temperature_K=raw["temperature_K"],
        gas_constant_J_mol_K=raw["gas_constant_J_mol_K"],
    )
    t, p = chemistry.bind(
        raw["reactions"],
        raw["growth"],
        raw["species_ids"],
        raw["species_valence"],
        raw["compartment_zones"] + ["padding"] * compartment_padding,
        **args,
    )
    if padding:
        t, p = chemistry.bind(
            raw["reactions"],
            raw["growth"],
            raw["species_ids"],
            raw["species_valence"],
            raw["compartment_zones"] + ["padding"] * compartment_padding,
            route_capacity=t.kind.size + padding,
            **args,
        )
    return raw, c, volume, t, p


def close(actual, expected, *, material=False):
    np.testing.assert_allclose(
        actual,
        expected,
        rtol=TOL["relative"],
        atol=TOL["material_atol_fmol"] if material else TOL["rate_atol_mM_s"],
    )


@pytest.mark.parametrize("raw", CASES, ids=lambda r: r["name"])
def test_native_and_independent_correspondence(raw):
    raw, c, volume, t, p = prepare(raw)
    assert chemistry.domain_valid(c, volume, t, p, xp=np)
    result = chemistry.rates(c, volume, t, p, xp=np)
    expected = reference.evaluate(raw)
    native = captured(raw["name"])
    assert native["status"] == "passed"
    assert len(expected["routes"]) == t.kind.size
    for key, actual in result._asdict().items():
        close(actual, [r[key] for r in expected["routes"]], material=key == "extent_fmol_s")
    for i, route in enumerate(native["routes"]):
        assert route["owner"] == t.owner[i]
        close(result.concentration_rate_mM_s[i], route["concentration_rate_mM_s"])
        if route["kind"] == "growth":
            close(result.growth_optimization_alpha[i], route["growth_optimization_alpha"])
            close(result.decay_optimization_mM_s[i], route["decay_optimization_mM_s"])
    ledger = chemistry.accounting(result.extent_fmol_s, t, xp=np)
    close(ledger.total_change_fmol, expected["amount_fmol_s"], material=True)
    close(ledger.total_change_fmol, native["amount_fmol_s"], material=True)
    close(ledger.growth_source_sink_fmol, expected["growth_source_sink_fmol_s"], material=True)
    close(ledger.reaction_conversion_fmol, expected["reaction_conversion_fmol_s"], material=True)
    for zone, kinds in (
        ("cell", (chemistry.GROWTH, chemistry.CELL)),
        ("mit", (chemistry.MIT,)),
        ("env", (chemistry.ENV,)),
    ):
        owner = next(i for i, name in enumerate(raw["compartment_zones"]) if name == zone)
        selection = np.isin(t.kind, kinds) & (t.owner == owner)
        np.testing.assert_array_equal(
            t.stoichiometry[:, selection],
            np.asarray(native["matrices"][zone]).reshape(len(SPECIES), -1),
        )
    evidence(
        raw["name"],
        dict(
            status="passed",
            input=raw,
            routes=expected["routes"],
            amount_fmol_s=ledger.total_change_fmol.tolist(),
            source_sink_fmol_s=ledger.growth_source_sink_fmol.tolist(),
        ),
    )


@pytest.mark.parametrize("zone", ("cell", "mit", "env"))
def test_reversible_zone_saturation_semantics(zone):
    lo = next(r for r in CASES if r["name"] == "product-km-" + zone + "-0.02")
    hi = next(r for r in CASES if r["name"] == "product-km-" + zone + "-40.0")
    _, c, v, t, p = prepare(lo)
    left = chemistry.rates(c, v, t, p, xp=np)
    # Km lives in topology, so bind and compare both independently.
    _, c2, v2, t2, p2 = prepare(hi)
    right = chemistry.rates(c2, v2, t2, p2, xp=np)
    if zone == "mit":
        assert np.max(np.abs(left.concentration_rate_mM_s - right.concentration_rate_mM_s)) > 1e-3
    else:
        np.testing.assert_array_equal(left.concentration_rate_mM_s, right.concentration_rate_mM_s)
    assert np.max(np.abs(left.backward_saturation - right.backward_saturation)) > 0.5


def test_literal_quotient_conversion_and_cell_forward_omission():
    raw = base()
    raw["reactions"] = [reaction(**{"reactant multipliers": [2.0], "standard free energy": -700.0})]
    _, c, v, t, p = prepare(raw)
    actual = chemistry.rates(c, v, t, p, xp=np)
    a, b = c[SPECIES.index("A"), :2], c[SPECIES.index("B"), :2]
    close(np.exp(actual.log_source_quotient), b / a**2)
    corrected = (1e-3 * b) / (1e-3 * a) ** 2
    close(corrected / np.exp(actual.log_source_quotient), np.full(2, 1000.0))
    altered = deepcopy(raw)
    altered["reactions"][0]["Km reactants"] = [1e6]
    _, c2, v2, t2, p2 = prepare(altered)
    changed = chemistry.rates(c2, v2, t2, p2, xp=np)
    np.testing.assert_array_equal(actual.concentration_rate_mM_s, changed.concentration_rate_mM_s)
    assert np.max(actual.forward_saturation - changed.forward_saturation) > 0.5


@pytest.mark.parametrize(
    "raw",
    [
        r
        for r in CASES
        if r["name"] in ("growth-matrix-order", "multi-real-coefficients-mit", "empty-network")
    ],
    ids=lambda r: r["name"],
)
def test_neutral_padding_and_explicit_owner_amounts(raw):
    _, c, v, t, p = prepare(raw)
    _, cp, vp, tp, pp = prepare(raw, padding=3, compartment_padding=2)
    expected = chemistry.rates(c, v, t, p, xp=np)
    padded = chemistry.rates(cp, vp, tp, pp, xp=np)
    assert chemistry.domain_valid(cp, vp, tp, pp, xp=np)
    for actual, wanted in zip(padded, expected, strict=True):
        np.testing.assert_array_equal(actual[:-3], wanted)
        np.testing.assert_array_equal(actual[-3:], 0.0)
    left = chemistry.accounting(expected.extent_fmol_s, t, xp=np)
    right = chemistry.accounting(padded.extent_fmol_s, tp, xp=np)
    np.testing.assert_array_equal(right.total_change_fmol[:, :-2], left.total_change_fmol)
    np.testing.assert_array_equal(right.total_change_fmol[:, -2:], 0.0)


def test_batch_broadcast_and_volume_units():
    raw = next(r for r in CASES if r["name"] == "growth-matrix-order")
    _, c, v, t, p = prepare(raw)
    state = np.stack((c, c * 1.3))
    volumes = np.stack((v, v * 2.0))
    params = p._replace(temperature_K=np.array([[307.0], [290.0]]))
    batched = chemistry.rates(state, volumes, t, params, xp=np)
    for i in range(2):
        separate = chemistry.rates(
            state[i], volumes[i], t, p._replace(temperature_K=np.array([307.0, 290.0])[i]), xp=np
        )
        for left, right in zip(batched, separate, strict=True):
            close(left[i], right, material=True)
    doubled = chemistry.rates(c, v * 2, t, p, xp=np)
    normal = chemistry.rates(c, v, t, p, xp=np)
    np.testing.assert_array_equal(doubled.concentration_rate_mM_s, normal.concentration_rate_mM_s)
    close(doubled.extent_fmol_s, normal.extent_fmol_s * 2, material=True)


def test_growth_source_sink_and_declared_moieties():
    raw = next(r for r in CASES if r["name"] == "growth-matrix-order")
    _, c, v, t, p = prepare(raw)
    result = chemistry.rates(c, v, t, p, xp=np)
    initial = c * v / 1e-15
    ledger = chemistry.accounting(result.extent_fmol_s * raw["dt_s"], t, xp=np)
    current = initial + ledger.total_change_fmol
    close(
        chemistry.material_residual(initial, current, result.extent_fmol_s * raw["dt_s"], t, xp=np),
        np.zeros_like(c),
        material=True,
    )
    weights = np.array(
        [
            [0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            raw["species_valence"],
        ]
    )
    projected = chemistry.projected_changes(result.extent_fmol_s, t, weights, xp=np)
    np.testing.assert_array_equal(projected[:, t.kind != chemistry.GROWTH], 0.0)
    close(
        np.sum(projected, axis=-1),
        weights
        @ np.sum(
            chemistry.accounting(result.extent_fmol_s, t, xp=np).growth_source_sink_fmol, axis=-1
        ),
        material=True,
    )
    assert np.any(projected != 0)
    evidence(
        "source-sink-ledger",
        dict(
            dt_s=raw["dt_s"],
            route_extents_fmol=(result.extent_fmol_s * raw["dt_s"]).tolist(),
            source_sink_fmol=ledger.growth_source_sink_fmol.tolist(),
            max_material_residual_fmol=float(
                np.max(np.abs(current - initial - ledger.total_change_fmol))
            ),
            projected_fmol_s=projected.tolist(),
        ),
    )


def test_unbalanced_reaction_remains_explicit():
    raw = base()
    raw["reactions"] = [reaction(**{"reactants": ["Na"]})]
    _, c, v, t, p = prepare(raw)
    result = chemistry.rates(c, v, t, p, xp=np)
    ledger = chemistry.accounting(result.extent_fmol_s, t, xp=np)
    projected = chemistry.projected_changes(
        result.extent_fmol_s, t, np.asarray(raw["species_valence"])[None, :], xp=np
    )
    close(projected[0], -result.extent_fmol_s, material=True)
    close(ledger.charge_change_in_elementary_fmol[:2], -result.extent_fmol_s, material=True)
    np.testing.assert_array_equal(ledger.growth_source_sink_fmol, 0.0)


def test_growth_scale_time_modulation_and_auxiliary_contract():
    raw = base()
    raw.update(reactions=[], growth=[molecule()])
    _, c, v, t, p = prepare(raw)
    actual = chemistry.rates(c, v, t, p, xp=np)
    scaled = chemistry.rates(c, v, t, p._replace(growth_scale=p.growth_scale * 2), xp=np)
    close(actual.production_mM_s, scaled.production_mM_s)
    close(actual.basal_decay_mM_s / 2, scaled.basal_decay_mM_s)
    close(actual.regulated_decay_mM_s / 2, scaled.regulated_decay_mM_s)
    accelerated = chemistry.rates(c, v, t, p._replace(time_factor=p.time_factor * 2), xp=np)
    close(accelerated.concentration_rate_mM_s, actual.concentration_rate_mM_s * 2)
    close(actual.growth_optimization_alpha, np.ones(2))
    close(actual.decay_optimization_mM_s, actual.basal_decay_mM_s)
    assert np.any(actual.production_mM_s != actual.growth_optimization_alpha)
    signed = chemistry.rates(c, v, t, p._replace(growth_modulation=-p.growth_modulation), xp=np)
    assert chemistry.domain_valid(
        c, v, t, p._replace(growth_modulation=-p.growth_modulation), xp=np
    )
    close(signed.production_mM_s, -actual.production_mM_s)


@pytest.mark.parametrize("raw", limitations(), ids=lambda r: r["name"])
def test_native_limitations_are_preserved(raw):
    record = captured(raw["name"])
    assert record["status"] == (
        "captured_failure" if raw["expected_failure"] else "captured_limitation"
    )
    if raw["name"] == "disabled-mito-fallback":
        assert record["reader_zones"]["cell"] == {"convert": "mit"}
        assert record["reader_zones"]["mit"] == {}
    elif raw["name"] == "duplicate-overwrite":
        assert len(record["routes"]) == 2
        assert ".vmax" in record["expressions"]["reactions"]["cell"]["convert"]
    elif raw["name"] == "zero-reversible-substrate":
        assert record["routes"][0]["concentration_rate_mM_s"] == "-inf"
    elif raw["name"] == "negative-growth-scale":
        assert all(row["concentration_rate_mM_s"] > 0 for row in record["routes"])
    if raw["name"] not in ("disabled-mito-fallback", "zero-reversible-substrate"):
        with pytest.raises((ValueError, TypeError)):
            prepare(raw)


@pytest.mark.parametrize(
    "change",
    ("negative", "nan", "inf", "zero-substrate", "zero-volume", "nan-volume", "negative-volume"),
)
def test_invalid_state_rejected_without_mutation(change):
    _, c, v, t, p = prepare()
    if change in ("negative", "nan", "inf", "zero-substrate"):
        c[1, 0] = {"negative": -0.1, "nan": np.nan, "inf": np.inf, "zero-substrate": 0.0}[change]
    else:
        v[0] = {"zero-volume": 0.0, "nan-volume": np.nan, "negative-volume": -1.0}[change]
    before, vb = c.copy(), v.copy()
    with np.errstate(all="ignore"):
        assert not chemistry.domain_valid(c, v, t, p, xp=np)
    np.testing.assert_array_equal(c, before)
    np.testing.assert_array_equal(v, vb)


@pytest.mark.parametrize(
    "field,value",
    (
        ("maximum_mM_s", -0.1),
        ("standard_free_energy_J_mol", 3.0),
        ("temperature_K", 0.0),
        ("gas_constant_J_mol_K", -1.0),
        ("growth_scale", 0.0),
        ("time_factor", np.inf),
        ("basal_decay_per_s", -0.2),
        ("growth_modulation", np.nan),
    ),
)
def test_invalid_parameters_rejected(field, value):
    _, c, v, t, p = prepare()
    original = np.asarray(getattr(p, field))
    bad = p._replace(**{field: np.full(original.shape, value)})
    with pytest.raises(ValueError):
        chemistry.validate_parameters(bad, t)
    with np.errstate(all="ignore"):
        assert not chemistry.domain_valid(c, v, t, bad, xp=np)


@pytest.mark.parametrize(
    "variant",
    (
        "unknown-owner",
        "matrix-forged",
        "zone-forged",
        "nonboolean-flag",
        "padding-state",
        "padding-rate",
        "wrong-temperature-axis",
        "wrong-state-shape",
    ),
)
def test_invalid_topology_padding_and_shapes(variant):
    _, c, v, t, p = prepare(padding=1, compartment_padding=1)
    if variant == "unknown-owner":
        t = t._replace(owner=np.full(t.owner.shape, 999))
    elif variant == "matrix-forged":
        t = t._replace(stoichiometry=t.stoichiometry + 0.2)
    elif variant == "zone-forged":
        t = t._replace(kind=np.full(t.kind.shape, chemistry.MIT))
    elif variant == "nonboolean-flag":
        p = p._replace(reversible=p.reversible.astype(int))
    elif variant == "padding-state":
        c[:, -1] = 1.0
    elif variant == "padding-rate":
        maximum = p.maximum_mM_s.copy()
        maximum[-1] = 1.0
        p = p._replace(maximum_mM_s=maximum)
    elif variant == "wrong-temperature-axis":
        p = p._replace(temperature_K=np.ones(3))
    else:
        c = c[:-1]
    with np.errstate(all="ignore"):
        assert not chemistry.domain_valid(c, v, t, p, xp=np)


def test_explicit_maps_controls_and_identity_validation():
    raw = next(r for r in CASES if r["name"] == "growth-zoned-regulation")
    invalid = deepcopy(raw)
    invalid["cell_to_environment"] = {}
    with pytest.raises(ValueError, match="explicit environment map"):
        prepare(invalid)
    invalid = deepcopy(raw)
    invalid["growth_targets"] = {}
    with pytest.raises(ValueError, match="target masks"):
        prepare(invalid)
    invalid = deepcopy(raw)
    invalid["growth_modulation"] = {}
    with pytest.raises(ValueError, match="sampled values"):
        prepare(invalid)
    invalid = deepcopy(raw)
    invalid["species_ids"][0] = invalid["species_ids"][1]
    with pytest.raises(ValueError, match="unique"):
        prepare(invalid)


def test_native_constants_and_authenticated_independence():
    record = captured("modern-gas-constant-explicit")
    folder = Path(os.environ["CELLS_BETSE_REACTIONS_NATIVE_CAPTURE"])
    manifest = json.loads((folder / "source-manifest.json").read_text())
    assert manifest["component_cases"] == len(CASES) == 38
    assert manifest["limitations"] == len(limitations()) == 11
    assert manifest["native_default_R_J_mol_K"] == chemistry.NATIVE_R == 8.314
    assert not manifest["production_cells_imported"] and not manifest["jax_imported"]
    for relative, expected in PROTOCOL["native_source"]["source_sha256"].items():
        assert hashlib.sha256((folder / "upstream" / relative).read_bytes()).hexdigest() == expected
    raw = deepcopy(record["input"])
    _, c, v, t, modern = prepare(raw)
    native = modern._replace(gas_constant_J_mol_K=np.asarray([chemistry.NATIVE_R]))
    left, right = (chemistry.rates(c, v, t, p, xp=np) for p in (modern, native))
    assert np.max(np.abs(left.concentration_rate_mM_s - right.concentration_rate_mM_s)) > 1e-6
    source = (ROOT / "validation/chemistry/betse_network_reactions_reference.py").read_text()
    assert (
        "import numpy" not in source and "import jax" not in source and "from cells" not in source
    )


def test_negative_euler_trial_is_rejected_and_rate_is_unclipped():
    _, c, v, t, p = prepare()
    result = chemistry.rates(c, v, t, p, xp=np)
    amount_rate = chemistry.accounting(result.extent_fmol_s, t, xp=np).total_change_fmol
    trial = c + 1000.0 * amount_rate * 1e-15 / v
    assert np.any(trial < 0)
    with np.errstate(all="ignore"):
        assert not chemistry.domain_valid(trial, v, t, p, xp=np)
    assert chemistry.domain_valid(c, v, t, p, xp=np)


def test_linear_growth_physical_time_and_euler_order():
    raw = base("linear-growth-clock")
    raw.update(reactions=[], growth=[molecule()])
    _, c, v, t, p = prepare(raw)
    tau = reference.linear_growth_exact(raw, 0.0)["tau_s"]
    species = SPECIES.index("C")
    initial_amount = c * v / 1e-15

    def integrate(intervals_per_tau, tau_count):
        state, extents = c.copy(), np.zeros(t.kind.size)
        dt = tau / intervals_per_tau
        for _ in range(intervals_per_tau * tau_count):
            transfer = chemistry.rates(state, v, t, p, xp=np).extent_fmol_s * dt
            state += chemistry.accounting(transfer, t, xp=np).total_change_fmol * 1e-15 / v
            extents += transfer
        assert chemistry.domain_valid(state, v, t, p, xp=np)
        residual = chemistry.material_residual(initial_amount, state * v / 1e-15, extents, t, xp=np)
        close(residual, np.zeros_like(c), material=True)
        return state[species, :2], float(np.max(np.abs(residual)))

    exact = np.asarray(reference.linear_growth_exact(raw, 3 * tau)["concentration_mM"])
    errors, residuals = [], []
    for intervals in (16, 32, 64):
        final, residual = integrate(intervals, 3)
        errors.append(float(np.max(np.abs(final - exact))))
        residuals.append(residual)
    orders = np.log2(np.asarray(errors[:-1]) / np.asarray(errors[1:]))
    assert np.all((orders > 0.98) & (orders < 1.05))
    settled, residual = integrate(32, 12)
    steady = np.asarray(reference.linear_growth_exact(raw, 12 * tau)["steady_mM"])
    relative_remaining = np.max(np.abs((settled - steady) / (c[species, :2] - steady)))
    assert relative_remaining < 1e-5
    evidence(
        "linear-growth-clock",
        dict(
            status="passed",
            input=raw,
            tau_s=tau,
            convergence_time_s=3 * tau,
            convergence_steps=[48, 96, 192],
            errors_mM=errors,
            orders=orders.tolist(),
            settling_time_s=12 * tau,
            settling_steps=384,
            final_mM=settled.tolist(),
            steady_mM=steady.tolist(),
            remaining_fraction=float(relative_remaining),
            max_material_residual_fmol=max(*residuals, residual),
            scope="Unregulated local growth only; no whole network/tissue settling claim",
        ),
    )


def test_near_equilibrium_reversible_branch_and_fractional_charge_metadata():
    for zone in ("cell", "env"):
        raw = base()
        raw["species_valence"] = [12.5, 0.0, 0.0, 0.0, -1.0, 1.0, 0.0]
        raw["reactions"] = [reaction(zone, **{"standard free energy": 0.0})]
        _, c, v, t, p = prepare(raw)
        q = chemistry.rates(c, v, t, p, xp=np).log_source_quotient
        energy = -q * raw["gas_constant_J_mol_K"] * raw["temperature_K"]
        near = p._replace(standard_free_energy_J_mol=energy)
        value = chemistry.rates(c, v, t, near, xp=np).concentration_rate_mM_s
        close(value, np.zeros_like(value))
        assert chemistry.domain_valid(c, v, t, near, xp=np)
        assert np.isfinite(t.species_valence).all()


def test_cpu_jax_rates_batching_and_declared_balance():
    import jax
    import jax.numpy as jnp

    raw = next(r for r in CASES if r["name"] == "growth-matrix-order")
    _, c, v, t, p = prepare(raw, padding=2, compartment_padding=1)
    assert jax.config.x64_enabled
    assert all(device.platform == "cpu" for device in jax.devices())
    t, p = (jax.tree.map(jnp.asarray, value) for value in (t, p))
    compiled = jax.jit(lambda state, volume: chemistry.rates(state, volume, t, p))
    batch_c, batch_v = np.stack((c, c * 1.3)), np.stack((v, v * 2))
    result = compiled(batch_c, batch_v)
    expected = chemistry.rates(batch_c, batch_v, t, p, xp=np)
    for left, right in zip(result, expected, strict=True):
        close(left, right, material=True)
    converted = jax.jit(lambda extents: chemistry.accounting(extents, t))(result.extent_fmol_s)
    close(
        converted.total_change_fmol,
        chemistry.accounting(expected.extent_fmol_s, t, xp=np).total_change_fmol,
        material=True,
    )
    evidence(
        "jax-batch",
        dict(
            status="passed", backend=jax.default_backend(), shape=list(result.extent_fmol_s.shape)
        ),
    )


def test_cpu_jax_singular_world_predicate_and_padding():
    import jax
    import jax.numpy as jnp

    _, c, v, t, p = prepare(padding=1, compartment_padding=1)
    t, p = (jax.tree.map(jnp.asarray, value) for value in (t, p))
    singular = c.copy()
    singular[1, 0] = 0.0
    worlds = jnp.asarray(np.stack((c, singular, c)))
    valid = jax.jit(jax.vmap(lambda state: chemistry.domain_valid(state, jnp.asarray(v), t, p)))(
        worlds
    )
    np.testing.assert_array_equal(valid, [True, False, True])
    actual = jax.jit(
        jax.vmap(lambda state: chemistry.rates(state, jnp.asarray(v), t, p).extent_fmol_s)
    )(worlds)
    np.testing.assert_array_equal(actual[0], actual[2])
    assert np.isfinite(actual[0]).all()
    np.testing.assert_array_equal(actual[:, -1], 0.0)


def test_cpu_jax_scan_restart_and_material():
    import jax
    import jax.numpy as jnp

    raw = next(r for r in CASES if r["name"] == "growth-matrix-order")
    _, c, v, t, p = prepare(raw)
    t, p = (jax.tree.map(jnp.asarray, value) for value in (t, p))
    volume, dt = jnp.asarray(v), 0.01
    initial = jnp.asarray(c * v / 1e-15)

    def body(carry, _):
        amount, extents = carry
        state = amount * 1e-15 / volume
        result = chemistry.rates(state, volume, t, p)
        transfer = result.extent_fmol_s * dt
        change = chemistry.accounting(transfer, t).total_change_fmol
        return (amount + change, extents + transfer), chemistry.domain_valid(state, volume, t, p)

    def run(carry, steps):
        return jax.lax.scan(body, carry, xs=None, length=steps)

    starting = (initial, jnp.zeros(t.kind.size))
    full, valid = jax.jit(lambda carry: run(carry, 8))(starting)
    half, _ = jax.jit(lambda carry: run(carry, 4))(starting)
    restarted, rest_valid = jax.jit(lambda carry: run(carry, 4))(half)
    np.testing.assert_array_equal(full[0], restarted[0])
    np.testing.assert_array_equal(full[1], restarted[1])
    assert np.asarray(valid).all() and np.asarray(rest_valid).all()
    residual = chemistry.material_residual(initial, full[0], full[1], t)
    close(residual, np.zeros_like(c), material=True)
    evidence(
        "jax-restart",
        dict(
            status="passed",
            steps=8,
            dt_s=dt,
            physical_time_s=8 * dt,
            max_material_residual_fmol=float(jnp.max(jnp.abs(residual))),
            checkpoint_exact=True,
            checkpoint_scope=(
                "Explicit local amount/extents carry only; "
                "shared checkpoint schema remains caller-owned"
            ),
        ),
    )


def test_cpu_jax_regulation_derivative():
    import jax
    import jax.numpy as jnp

    raw = next(r for r in CASES if r["name"] == "ordinary-independent-mit")
    _, c, v, t, p = prepare(raw)
    t, p = (jax.tree.map(jnp.asarray, value) for value in (t, p))
    index, owner = SPECIES.index("Y"), 2

    def scalar(value):
        state = jnp.asarray(c).at[index, owner].set(value)
        return chemistry.rates(state, jnp.asarray(v), t, p).concentration_rate_mM_s[0]

    center = c[index, owner]
    derivative = float(jax.jit(jax.grad(scalar))(center))
    h = 1e-4
    finite = float((scalar(center + h) - scalar(center - h)) / (2 * h))
    np.testing.assert_allclose(derivative, finite, rtol=2e-8, atol=1e-12)
    assert np.isfinite(derivative) and derivative != 0
    evidence(
        "jax-gradient",
        dict(
            status="passed",
            species="Y",
            owner=owner,
            derivative=derivative,
            finite_difference=finite,
            step_mM=h,
        ),
    )
