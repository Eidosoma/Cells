"""Resolved charge/current closure: independent roots, source work and device parity."""

import copy
import json
import os
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.numerics import surface_field as model
from cells.numerics import tissue_field as legacy
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from validation.tissue import surface_field_fixtures as fixtures
from validation.tissue import surface_field_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
PROTOCOL = json.loads(Path(fixtures.__file__).with_name("surface_field_protocol.json").read_text())
TOL = PROTOCOL["tolerances"]


def evidence(name, report, arrays=None):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + ".json")).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(path / (name + ".npz"), **arrays)


def atol(name):
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
            return TOL[key]
    return TOL["flux_atol_fmol_s"]


def compare(actual, expected):
    for key, target in expected.items():
        np.testing.assert_allclose(
            actual[key], target, rtol=TOL["physical_rtol"], atol=atol(key), err_msg=key
        )


def physical(values):
    excluded = {
        "charge_residual_C",
        "charge_normalized",
        "component_current_residual_A",
        "current_normalized",
        "energy_balance_pJ_s",
        "rates",
        "iterations",
        "converged",
    }
    result = {k: v for k, v in values._asdict().items() if k not in excluded}
    result.update({"rates__" + k: v for k, v in values.rates._asdict().items() if k != "valid"})
    return result


@pytest.fixture(scope="module")
def device():
    jax.config.update("jax_enable_x64", True)
    return jax.devices(BACKEND)[0]


def selected(args, device, **options):
    function = jax.jit(model.solve, static_argnames=("max_iterations", "max_backtracks"))
    result = jax.block_until_ready(function(*jax.device_put(args, device), **options))
    assert all(v.device.platform == BACKEND for v in jax.tree.leaves(result))
    assert all(v.dtype == jnp.float64 for v in physical(result).values())
    return jax.tree.map(np.asarray, result)


@pytest.fixture(scope="module")
def computed(device):
    return {
        name: selected(fixtures.arrays(fixtures.definition(name)), device)
        for name in fixtures.CASES
    }


@pytest.mark.parametrize("name", fixtures.CASES)
def test_independent_field_and_open_system_accounting(name, computed):
    raw, actual = fixtures.definition(name), computed[name]
    assert actual.converged and actual.rates.valid
    assert actual.current_normalized <= model.NEWTON_TARGET and actual.charge_normalized <= 1
    expected, solved = reference.solve(raw)
    compare({"potential_V": actual.potential_V}, {"potential_V": expected})
    expected_rates, accounting = reference.check(raw, actual)
    compare(actual.rates._asdict(), expected_rates)
    for prefix in ("membrane", "junction", "face"):
        assert np.min(getattr(actual.rates, prefix + "_dissipation_pJ_s"), initial=0) >= -1e-15
    evidence(
        name,
        {
            "status": "passed",
            "inputs": raw,
            "independent": solved,
            "accounting": accounting,
            "iterations": int(actual.iterations),
            "current_normalized": float(actual.current_normalized),
            "charge_normalized": float(actual.charge_normalized),
        },
        physical(actual),
    )


def test_analytic_clamped_divider_and_equilibrium(computed):
    actual = computed["all_clamped"]
    np.testing.assert_allclose(actual.potential_V[0], -0.0363, rtol=0, atol=3e-17)
    np.testing.assert_allclose(
        actual.rates.membrane_voltage_V[:2], [-0.0383, -0.0323], rtol=0, atol=3e-17
    )
    assert actual.component_current_residual_A.size == 0
    eq = computed["equilibrium"]
    np.testing.assert_array_equal(eq.potential_V, 0)
    np.testing.assert_array_equal(eq.rates.cell_rate_fmol_s, 0)
    np.testing.assert_array_equal(eq.rates.outside_rate_fmol_s, 0)
    assert eq.dissipation_pJ_s == 0


def test_clamp_gauge_shift_preserves_total_source_work(device, computed):
    raw = fixtures.definition("anchored")
    raw["boundary_V"] = np.where(
        raw["layout"]["reservoir"], np.asarray(raw["boundary_V"]) + 0.013, 0
    ).tolist()
    actual = selected(fixtures.arrays(raw), device)
    old = computed["anchored"]
    assert actual.converged
    expected = physical(old)
    for key in ("electrode_power_pJ_s", "reservoir_power_pJ_s"):
        expected.pop(key)
    expected["potential_V"] = old.potential_V + 0.013
    compare(physical(actual), expected)
    np.testing.assert_allclose(
        actual.electrode_power_pJ_s + actual.reservoir_power_pJ_s,
        old.electrode_power_pJ_s + old.reservoir_power_pJ_s,
        rtol=3e-12,
        atol=3e-12,
    )
    assert abs(actual.electrode_power_pJ_s - old.electrode_power_pJ_s) > 1e-4
    reference.check(raw, actual)


def test_closed_gauge_change(device, computed):
    raw = fixtures.definition("closed")
    raw["gauge_mask"] = [True, False, False, False, False]
    actual = selected(fixtures.arrays(raw), device)
    old = computed["closed"]
    assert actual.converged
    expected = physical(old)
    expected["potential_V"] = old.potential_V - old.potential_V[2]
    compare(physical(actual), expected)


def test_patch_subdivision_padding_and_actual_controls(computed):
    old = computed["open"]
    for name in ("split", "padded"):
        actual = computed[name]
        phi = actual.potential_V if name == "split" else actual.potential_V[[0, 1, 3, 4, 5, 6, 7]]
        np.testing.assert_allclose(phi, old.potential_V, rtol=3e-12, atol=3e-13)
        for key in (
            "capacitor_energy_pJ",
            "capacitor_energy_rate_pJ_s",
            "electrode_power_pJ_s",
            "reservoir_power_pJ_s",
            "dissipation_pJ_s",
        ):
            np.testing.assert_allclose(
                getattr(actual, key), getattr(old, key), rtol=3e-12, atol=3e-12
            )
    padded = computed["padded"]
    np.testing.assert_array_equal(padded.potential_V[[2, 8]], 0)
    np.testing.assert_array_equal(padded.rates.cell_rate_fmol_s[:, -1], 0)
    np.testing.assert_array_equal(padded.rates.outside_rate_fmol_s[:, -1], 0)
    blocked = computed["blocked"]
    np.testing.assert_array_equal(blocked.rates.junction_flux_fmol_s, 0)
    np.testing.assert_array_equal(blocked.rates.membrane_flux_fmol_s, 0)
    assert np.max(abs(blocked.potential_V - old.potential_V)) > 1e-7


def test_one_owner_reduces_to_qualified_tissue_field(device, computed):
    raw = fixtures.definition("one_owner")
    ci, co, charge, _, _, opened, _, p = fixtures.arrays(raw)
    s = p.surface
    old_layout = legacy.validate_layout(
        legacy.Layout(
            s.temperature,
            s.valence,
            s.cell_active,
            np.asarray([0, 2]),
            s.outside_active,
            np.asarray(raw["gauge_mask"]),
            s.face_active,
            s.face_sender,
            s.face_receiver,
            s.face_factor,
            s.junction_active,
            s.junction_sender,
            s.junction_receiver,
            s.junction_area,
            s.junction_permeability,
        )
    )
    cap = np.asarray([sum(s.membrane_capacitance[s.membrane_cell == i]) for i in range(2)])
    old = jax.block_until_ready(
        jax.jit(legacy.solve)(
            *jax.device_put(
                (ci, co, charge / cap, opened, np.ones_like(opened), old_layout), device
            )
        )
    )
    assert bool(old.converged)
    actual = computed["one_owner"]
    np.testing.assert_allclose(actual.potential_V[2:], old.potential_V, rtol=3e-10, atol=3e-13)
    np.testing.assert_allclose(actual.potential_V[:2], old.cell_potential_V, rtol=3e-10, atol=3e-13)
    np.testing.assert_allclose(
        actual.rates.junction_flux_fmol_s, old.junction_flux_fmol_per_s, rtol=3e-10, atol=3e-12
    )
    evidence("legacy-reduction", {"status": "passed", "law": legacy.LAW_ID})


def test_capacitor_energy_derivative_from_independent_perturbations(computed):
    reports = {}
    for name in ("closed", "anchored"):
        raw, actual = fixtures.definition(name), computed[name]
        z = np.asarray(raw["layout"]["valence"])
        cell_rate = CHARGE_PER_FMOL * np.sum(z * actual.rates.cell_rate_fmol_s, axis=0)
        outside_rate = CHARGE_PER_FMOL * np.sum(z * actual.rates.outside_rate_fmol_s, axis=0)
        dt, energies, voltages = 1e-6, [], []
        p = raw["layout"]
        for sign in (-1, 1):
            changed = copy.deepcopy(raw)
            changed["cell_charge_C"] = (
                np.asarray(raw["cell_charge_C"]) + sign * dt * cell_rate
            ).tolist()
            changed["outside_charge_C"] = (
                np.asarray(raw["outside_charge_C"]) + sign * dt * outside_rate
            ).tolist()
            phi, _ = reference.solve(changed)
            vm = phi[p["membrane_cell"]] - phi[2 + np.asarray(p["membrane_outside"])]
            energies.append(0.5e12 * np.sum(np.asarray(p["membrane_capacitance"]) * vm**2))
            voltages.append(vm)
        derivative = (energies[1] - energies[0]) / (2 * dt)
        np.testing.assert_allclose(
            derivative,
            actual.capacitor_energy_rate_pJ_s,
            rtol=3e-8,
            atol=TOL["energy_derivative_atol_pJ_s"],
        )
        np.testing.assert_allclose(
            (voltages[1] - voltages[0]) / (2 * dt),
            actual.membrane_voltage_rate_V_s,
            rtol=3e-8,
            atol=TOL["voltage_rate_atol_V_s"],
        )
        reports[name] = {"difference_pJ_s": float(derivative - actual.capacitor_energy_rate_pJ_s)}
    evidence(
        "capacitor-energy-derivative", {"status": "passed", "perturbation_s": dt, "cases": reports}
    )


@pytest.mark.parametrize(
    "fault",
    ["return_path", "missing_gauge", "extra_gauge", "inactive_reservoir", "no_charged_path"],
)
def test_invalid_field_definition_rejected(fault):
    raw = fixtures.definition("open")
    if fault == "return_path":
        raw["layout"]["face_factor"] = [[0.0] * 5 for _ in range(3)]
    elif fault == "missing_gauge":
        raw["layout"]["reservoir"] = [False] * 5
    elif fault == "extra_gauge":
        raw["gauge_mask"][0] = True
    elif fault == "inactive_reservoir":
        raw["layout"]["outside_active"][4] = False
    else:
        raw["layout"]["valence"] = [[0.0]] * 3
    with pytest.raises(ValueError):
        fixtures.arrays(raw)


@pytest.mark.parametrize(
    "fault",
    [
        "charge",
        "gauge_charge",
        "padding_charge",
        "boundary",
        "nan",
        "concentration",
        "gate",
        "voltage",
    ],
)
def test_incompatible_or_invalid_stage_rejected(fault, device):
    raw = fixtures.definition("padded" if fault == "padding_charge" else "closed")
    if fault == "charge":
        raw["outside_charge_C"][0] += 1e-16
    elif fault == "gauge_charge":
        raw["outside_charge_C"][4] += 1e-16
    elif fault == "padding_charge":
        raw["cell_charge_C"][-1] = 1e-16
    elif fault == "boundary":
        raw["boundary_V"][0] = 0.01
    elif fault == "nan":
        raw["cell_charge_C"][0] = float("nan")
    elif fault == "concentration":
        raw["co"][0][0] = 0
    elif fault == "gate":
        raw["junction_open"][0] = 1.1
    else:
        raw["cell_charge_C"][0] += 1e-8
        raw["outside_charge_C"][0] -= 1e-8
    actual = selected(fixtures.arrays(raw), device)
    assert not actual.converged


def test_exhausted_newton_solve_fails(device):
    actual = selected(fixtures.arrays(fixtures.definition("open")), device, max_iterations=0)
    assert not actual.converged and actual.iterations == 0 and actual.current_normalized > 1


def test_wrong_field_and_missing_source_ledgers_rejected(computed):
    for name in ("closed", "anchored", "open"):
        reference.check(fixtures.definition(name), computed[name])
    wrong = computed["closed"]._replace(
        potential_V=np.asarray(fixtures.definition("closed")["seed_potential_V"])
    )
    with pytest.raises(AssertionError):
        reference.check(fixtures.definition("closed"), wrong)
    actual = computed["anchored"]
    assert abs(actual.electrode_power_pJ_s) > 1e-4
    with pytest.raises(AssertionError):
        reference.check(
            fixtures.definition("anchored"),
            actual._replace(electrode_current_A=np.zeros_like(actual.electrode_current_A)),
        )
    actual = computed["open"]
    wrong = actual._replace(
        rates=actual.rates._replace(
            reservoir_supply_fmol_s=np.zeros_like(actual.rates.reservoir_supply_fmol_s)
        )
    )
    with pytest.raises(AssertionError):
        reference.check(fixtures.definition("open"), wrong)
    evidence(
        "negative-controls",
        {
            "status": "passed",
            "rejected": [
                "uncoupled field",
                "missing electrode current",
                "missing reservoir supply",
            ],
        },
    )


def test_batched_world_partition_replay(device):
    worlds = []
    for factor in (0.97, 1.0, 1.04, 1.07):
        raw = fixtures.definition("open")
        raw["ci"] = (np.asarray(raw["ci"]) * factor).tolist()
        worlds.append(fixtures.arrays(raw))
    arrays = jax.tree.map(lambda *v: np.stack(v), *worlds)
    # Match core.batch._batch_rollout: preserve each world's guarded execution
    # with lax.map. Direct vmap changes the GPU's batched arithmetic when the
    # cohort width changes; its physical agreement is checked separately below.
    fn = jax.jit(lambda rows: jax.lax.map(lambda world: model.solve(*world), rows))
    all_values = jax.block_until_ready(fn(jax.device_put(arrays, device)))
    assert np.all(all_values.converged)
    assert all(v.device.platform == BACKEND for v in jax.tree.leaves(all_values))
    pieces = []
    for start, end in ((0, 2), (2, 4)):
        part = jax.tree.map(lambda v, start=start, end=end: v[start:end], arrays)
        pieces.append(jax.block_until_ready(fn(jax.device_put(part, device))))
    joined = jax.tree.map(lambda *v: np.concatenate([np.asarray(a) for a in v]), *pieces)
    for key, value in physical(all_values).items():
        np.testing.assert_array_equal(value, physical(joined)[key])
    order = np.asarray([3, 1, 0, 2])
    shuffled = jax.tree.map(lambda v: v[order], arrays)
    reordered = jax.block_until_ready(fn(jax.device_put(shuffled, device)))
    for key, value in physical(all_values).items():
        np.testing.assert_array_equal(value[order], physical(reordered)[key])
    for i, args in enumerate(worlds):
        single = selected(args, device)
        compare({k: np.asarray(v)[i] for k, v in physical(all_values).items()}, physical(single))

    vectorized = jax.jit(jax.vmap(model.solve))
    vector_all = jax.block_until_ready(vectorized(*jax.device_put(arrays, device)))
    vector_parts = []
    for start, end in ((0, 2), (2, 4)):
        part = jax.tree.map(lambda v, start=start, end=end: v[start:end], arrays)
        vector_parts.append(jax.block_until_ready(vectorized(*jax.device_put(part, device))))
    vector_joined = jax.tree.map(
        lambda *v: np.concatenate([np.asarray(a) for a in v]), *vector_parts
    )
    compare(physical(vector_all), physical(vector_joined))
    compare(physical(vector_all), physical(all_values))
    for values in (joined, reordered, vector_all, vector_joined):
        assert np.all(values.converged) and np.all(values.rates.valid)
    for values in (all_values, vector_all, vector_joined):
        for i, factor in enumerate((0.97, 1.0, 1.04, 1.07)):
            raw = fixtures.definition("open")
            raw["ci"] = (np.asarray(raw["ci"]) * factor).tolist()
            one = jax.tree.map(lambda v, i=i: np.asarray(v)[i], values)
            expected, _ = reference.check(raw, one)
            compare(one.rates._asdict(), expected)
    deltas = {
        key: float(np.max(abs(np.asarray(value) - physical(vector_joined)[key]), initial=0))
        for key, value in physical(vector_all).items()
    }
    evidence(
        "batch-partitions",
        {
            "status": "passed",
            "worlds": 4,
            "partition": [2, 2],
            "reordered_world_indices": order.tolist(),
            "physical_replay": "bitwise",
            "replay_execution": "jax.lax.map, matching core.batch._batch_rollout",
            "direct_vmap_comparison": "original unit-specific numerical tolerances",
            "direct_vmap_partition_max_absolute_difference": deltas,
            "tolerances": TOL,
        },
        {
            prefix + "__" + key: np.asarray(value)
            for prefix, values in (
                ("mapped", all_values),
                ("vmap", vector_all),
                ("vmap_partitioned", vector_joined),
            )
            for key, value in physical(values).items()
        },
    )


def test_cpu_gpu_saved_fields():
    if BACKEND != "gpu":
        pytest.skip("CPU baseline is compared in the registered GPU phase")
    assert EVIDENCE
    count = 0
    for name in fixtures.CASES:
        with (
            np.load(Path(EVIDENCE) / "cpu" / (name + ".npz"), allow_pickle=False) as cpu,
            np.load(Path(EVIDENCE) / "gpu" / (name + ".npz"), allow_pickle=False) as gpu,
        ):
            assert set(cpu) == set(gpu)
            compare(gpu, cpu)
            count += sum(cpu[k].size for k in cpu)
    evidence("field-cpu-gpu", {"status": "passed", "physical_scalars": count, "tolerances": TOL})
