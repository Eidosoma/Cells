"""Compiled finite energy and water: full trajectories, guards and conservation."""

import json
import os
from functools import lru_cache
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly.engine import device_for
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.models import surface_energy_water as model
from cells.models import surface_tissue as passive
from cells.numerics.fixed_step import rk4_checked_step
from tests.unit.test_surface_repair_full import compare_backend
from tests.unit.test_surface_tissue import exact
from validation.tissue import surface_energy_water_fixtures as fixtures
from validation.tissue import surface_energy_water_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
PUBLISHED = os.environ.get("CELLS_COMPONENT_PUBLISHED_EVIDENCE")
PREFIX = "energy-water"
STEPS = (1.25e-6, 6.25e-7, 3.125e-7)
ENERGY_SPECIES = ("ATP", "ADP", "Pi")
POOL_ATOL_FMOL = 2e-12


def evidence(name, value, arrays=None):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        path = root / (PREFIX + "-" + name)
        path.with_suffix(".json").write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(path.with_suffix(".npz"), **arrays)


def initial(raw=None, *, time=0.0):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, layout = model.initial_values(spec)
    table = control_values(spec, [time])
    return spec, state, layout, type(table)(*(v[0] for v in table))


def error_budget(c, actual, expected, *, atol=2e-11, charge_atol=3e-25, rtol=3e-9):
    absolute = reference.flatten(
        c,
        {
            k: np.full(shape, charge_atol if k.endswith("_C") else atol)
            for k, shape in c["shapes"].items()
        },
    )
    ratio = np.abs(actual - expected) / (absolute + rtol * np.abs(expected))
    assert np.isfinite(ratio).all() and np.max(ratio, initial=0) <= 1
    return float(np.max(ratio, initial=0))


def test_compiled_rejection_keeps_every_field_unchanged():
    jax.config.update("jax_enable_x64", True)
    spec, state, p, control = initial(fixtures.definition("coupled"))
    device = device_for(BACKEND, 0)
    state, control, p = jax.device_put((state, control, p), device)
    step = jax.jit(
        lambda s, ctl, q, dt: rk4_checked_step(
            model.rhs, model.domain_valid, s, dt, ctl, q, q.active
        )
    )
    accepted, valid = step(state, control, p, np.float64(spec.execution.dt))
    assert bool(valid) and np.any(np.asarray(accepted.energy_amount_increment_fmol))
    # Explicitly test exhausted ATP even when pump and regeneration controls are off.
    increment = np.asarray(state.energy_amount_increment_fmol).copy()
    increment[0, 0] = -spec.model.energy_pools[0].initial_amount_fmol[0]
    exhausted = state._replace(energy_amount_increment_fmol=jax.device_put(increment, device))
    disabled = control._replace(pump=control.pump * 0.0, regeneration=control.regeneration * 0.0)
    volume = np.asarray(state.volume_increment_pL).copy()
    volume[0] = float(p.water_minimum_volume_pL[0] - p.volume[0])
    collapsed = state._replace(volume_increment_pL=jax.device_put(volume, device))
    cases = (
        (state, 100.0, control),
        (state, spec.execution.dt, control._replace(regeneration=control.regeneration * np.nan)),
        (exhausted, spec.execution.dt, disabled),
        (collapsed, spec.execution.dt, disabled._replace(water=control.water * 0.0)),
        (state, spec.execution.dt, control._replace(water=control.water * np.nan)),
    )
    for before, dt, ctl in cases:
        rejected, valid = step(before, ctl, p, np.float64(dt))
        assert not bool(valid)
        exact(rejected, before)
    evidence(
        "compiled-guard",
        dict(
            status="passed",
            backend=BACKEND,
            rejected_trials_preserved=True,
            exhausted_substrate_rejected_with_routes_off=True,
            complete_fields=28,
        ),
    )


def arrays(value):
    return dict(
        accepted_times=value.times,
        **{k: np.asarray(v) for k, v in value.history._asdict().items()},
        **{"observed_" + k: v for k, v in vars(value.observations).items()},
    )


@lru_cache(maxsize=None)
def trajectory(arm):
    spec = parse_spec(fixtures.definition(arm, backend=BACKEND))
    result = run(spec)
    evidence(
        "history-" + arm,
        dict(
            status="captured",
            inputs=fixtures.normalized(spec.to_dict()),
            diagnostics=result.diagnostics,
            timings=result.timings,
        ),
        arrays(result),
    )
    assert all(v.device.platform == BACKEND for v in result.final.state)
    return result


def saved(name, backend=BACKEND):
    for candidate in (EVIDENCE, PUBLISHED):
        if not candidate:
            continue
        path = Path(candidate) / backend / (PREFIX + "-" + name)
        if path.with_suffix(".json").exists():
            info = json.loads(path.with_suffix(".json").read_text())
            with np.load(path.with_suffix(".npz"), allow_pickle=False) as data:
                return info, {k: v.copy() for k, v in data.items()}
    raise AssertionError("Require saved finite-energy evidence: " + name + "/" + backend)


def independent(arm, raw, *, refinement=1):
    name = f"reference-{arm}-r{refinement}"
    inputs = fixtures.normalized(raw)
    if BACKEND == "gpu" and EVIDENCE:
        receipt, result = saved(name, "cpu")
        assert receipt["status"] == "passed" and receipt["inputs"] == inputs
        assert receipt["refinement"] == refinement
        evidence(name, receipt | dict(reused_cpu_reference=True), result)
    else:
        expected = reference.integrate(raw, refinement=refinement)
        result = dict(
            state=np.asarray(expected["state"]), potential_V=np.asarray(expected["potential_V"])
        )
        evidence(
            name,
            dict(
                status="passed",
                inputs=inputs,
                refinement=refinement,
                method=expected["method"],
                evaluations=expected["evaluations"],
            ),
            result,
        )
    return result


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_complete_trajectory_against_independent_reference(arm):
    value = trajectory(arm)
    raw = value.spec.to_dict()
    expected = independent(arm, raw)
    c = reference.bind(raw)
    actual = reference.flatten(c, vars(value.observations))
    evidence(
        "errors-" + arm,
        dict(inputs=raw),
        dict(actual=actual, reference=expected["state"], signed_error=actual - expected["state"]),
    )
    ratio = error_budget(c, actual, expected["state"])
    phi = np.c_[
        value.observations.cell_potential_V[:, : len(value.spec.model.cells)],
        value.observations.extracellular_potential_V[:, : len(value.spec.model.extracellular)],
    ]
    np.testing.assert_allclose(phi, expected["potential_V"], rtol=3e-9, atol=2e-8)
    stable = None
    if arm == "release":
        tighter = independent(arm, raw, refinement=4)
        stable = error_budget(
            c, expected["state"], tighter["state"], atol=3e-14, charge_atol=3e-28, rtol=3e-11
        )
    assert value.diagnostics["max_energy_balance_error_pJ"] <= passive.ENERGY_ATOL_PJ
    assert value.diagnostics["max_pool_internal_transfer_error_pJ"] <= passive.ENERGY_ATOL_PJ
    assert value.diagnostics["max_global_water_balance_error_pL"] <= model.VOLUME_ATOL_PL
    evidence(
        "trajectory-" + arm,
        dict(
            status="passed",
            inputs=fixtures.normalized(raw),
            max_error_over_budget=ratio,
            reference_stability_over_budget=stable,
            complete_fields=28,
            diagnostics=value.diagnostics,
        ),
    )


def test_three_grid_refinement():
    _, base = saved("history-release")
    raw = fixtures.definition("release", backend=BACKEND)
    c = reference.bind(raw)
    _, target = saved("reference-release-r4", "cpu")
    errors, ratios = [], []
    for i, dt in enumerate(STEPS):
        spec = parse_spec(fixtures.definition("release", backend=BACKEND, dt=dt))
        data = (
            {k.removeprefix("observed_"): v for k, v in base.items() if k.startswith("observed_")}
            if i == 0
            else vars(run(spec).observations)
        )
        actual = reference.flatten(c, data)
        evidence(
            f"grid-{i}",
            dict(inputs=spec.to_dict()),
            dict(actual=actual, reference=target["state"], signed_error=actual - target["state"]),
        )
        ratios.append(error_budget(c, actual, target["state"]))
        errors.append(float(np.max(np.abs(actual - target["state"]))))
    assert errors[-1] <= max(0.2 * errors[0], 3e-13)
    evidence(
        "refinement",
        dict(
            status="passed",
            steps_s=STEPS,
            max_absolute_errors=errors,
            max_error_over_budget=ratios,
        ),
    )


def test_saved_finite_pool_material_supply_and_controls():
    results, material_errors, supply_errors = {}, {}, {}
    for arm in fixtures.ARMS:
        receipt, data = saved("history-" + arm)
        raw = fixtures.normalized(parse_spec(fixtures.definition(arm)).to_dict())
        assert receipt["inputs"] == raw
        results[arm] = data
        m = raw["model"]
        cells = {cell["id"]: slot for slot, cell in enumerate(m["cells"])}
        pools = {pool["id"]: cells[pool["cell_id"]] for pool in m["energy_pools"]}
        net = np.zeros((len(data["accepted_times"]), len(cells)))
        for slot, patch in enumerate(m["membranes"]):
            if patch["pump"]:
                owner = pools[patch["pump"]["metabolism"]["pool_id"]]
                net[:, owner] += data["pump_cycles"][:, slot]
        for slot, port in enumerate(m["regeneration_ports"]):
            net[:, pools[port["pool_id"]]] -= data["regeneration_cycles_fmol"][:, slot]
        expected = np.stack((-net, net, net), axis=1)
        actual = data["energy_amount_increment_fmol"][:, :, : len(cells)]
        error = float(np.max(np.abs(actual - expected), initial=0.0))
        material_errors[arm] = error
        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=POOL_ATOL_FMOL)
        initial_amount = np.zeros((3, len(cells)))
        for pool in m["energy_pools"]:
            initial_amount[:, pools[pool["id"]]] = [
                pool["initial_amount_fmol"][species] for species in ENERGY_SPECIES
            ]
        assert np.all(initial_amount[None] + actual > 0.0)
        np.testing.assert_allclose(actual[:, 0] + actual[:, 1], 0.0, rtol=0.0, atol=POOL_ATOL_FMOL)
        np.testing.assert_allclose(
            3 * actual[:, 0] + 2 * actual[:, 1] + actual[:, 2],
            0.0,
            rtol=0.0,
            atol=POOL_ATOL_FMOL,
        )
        expected_work = np.zeros_like(data["regeneration_supplied_work_pJ"])
        for slot, port in enumerate(m["regeneration_ports"]):
            expected_work[:, slot] = (
                1e-3 * port["supplied_energy_J_per_mol"] * data["regeneration_cycles_fmol"][:, slot]
            )
        actual_work = data["regeneration_supplied_work_pJ"]
        supply_errors[arm] = float(np.max(np.abs(actual_work - expected_work), initial=0.0))
        np.testing.assert_allclose(actual_work, expected_work, rtol=3e-10, atol=3e-13)
        assert np.min(data["regeneration_dissipated_energy_pJ"], initial=0.0) >= -3e-13

    coupled, supply_off = results["coupled"], results["supply_off"]
    assert coupled["pump_cycles"][-1, 0] > 0.0
    assert results["reverse"]["pump_cycles"][-1, 0] < 0.0
    for field in ("pump_cycles", "pump_dissipated_energy_pJ", "metabolic_work_pJ"):
        assert not np.any(results["inhibited"][field])
    for field in (
        "regeneration_cycles_fmol",
        "regeneration_dissipated_energy_pJ",
        "regeneration_supplied_work_pJ",
    ):
        assert not np.any(supply_off[field])
    assert supply_off["energy_amount_increment_fmol"][-1, 0, 0] < 0.0
    assert (
        coupled["energy_amount_increment_fmol"][-1, 0, 0]
        > supply_off["energy_amount_increment_fmol"][-1, 0, 0]
    )
    assert coupled["pump_cycles"][-1, 0] != supply_off["pump_cycles"][-1, 0]
    release = results["release"]
    times = release["observed_times"]
    assert not np.any(
        release["observed_pump_cycle_rate_fmol_s"][(times >= 23.7e-6) & (times < 41.3e-6)]
    )
    assert not np.any(
        release["observed_channel_flux_fmol_s"][(times >= 17.3e-6) & (times < 37.1e-6)]
    )
    # Extent changes use the preceding, held control, so test complete accepted
    # intervals within the supply-off segment without relying on a readout alias.
    accepted = release["accepted_times"]
    off = (accepted[:-1] >= 13.3e-6) & (accepted[1:] <= 31.1e-6)
    assert np.any(off)
    for field in (
        "regeneration_cycles_fmol",
        "regeneration_dissipated_energy_pJ",
        "regeneration_supplied_work_pJ",
    ):
        assert not np.any(np.diff(release[field], axis=0)[off])
    evidence(
        "controls",
        dict(
            status="passed",
            finite_pool_material_errors_fmol=material_errors,
            regeneration_supply_identity_errors_pJ=supply_errors,
            supply_changes_pumping=True,
            reverse_cycles=True,
            independent_clocks=True,
            shared_pump_owner=True,
            synthetic=True,
            physiological_calibration=False,
        ),
    )


def test_cpu_gpu_complete_states_and_observations():
    if BACKEND == "cpu":
        pytest.skip("Requires recorded CPU and L4 histories")
    count = 0
    for arm in fixtures.ARMS:
        gpu_info, actual = saved("history-" + arm)
        cpu_info, expected = saved("history-" + arm, "cpu")
        assert gpu_info["inputs"] == cpu_info["inputs"]
        count += compare_backend(actual, expected)
    evidence("cpu-gpu", dict(status="passed", compared_values=count))


def test_saved_water_and_internal_volume_work_accounting():
    errors = {}
    for arm in fixtures.ARMS:
        receipt, data = saved("history-" + arm)
        raw = receipt["inputs"]
        spec = parse_spec(raw)
        _, p = model.initial_values(spec)
        state = model.STATE_TYPE(*(data[k] for k in model.STATE_TYPE._fields))
        checks = model.check_values(state, spec)
        errors[arm] = checks
        volume = p.volume + data["volume_increment_pL"]
        pools = p.energy_initial_amount_fmol + data["energy_amount_increment_fmol"]
        np.testing.assert_allclose(
            data["observed_pool_osmolyte_amount_fmol"],
            pools[
                [np.flatnonzero(data["accepted_times"] == t)[0] for t in data["observed_times"]]
            ].sum(axis=1),
            atol=2e-12,
            rtol=3e-10,
        )
        assert np.all(volume > p.water_minimum_volume_pL[: p.active.size])
        assert np.all(volume < p.water_maximum_volume_pL[: p.active.size])
        if arm == "sealed":
            assert all(not np.any(data[k]) for k in model.EXTRA_AXES)
        else:
            assert np.any(data["volume_increment_pL"])
            assert np.any(data["pool_volume_work_pJ"])
    _, release = saved("history-release")
    times = release["accepted_times"]
    off = (times[:-1] >= fixtures.WATER_RELEASE_TIMES[0]) & (
        times[1:] <= fixtures.WATER_RELEASE_TIMES[1]
    )
    assert np.any(off)
    for key in model.EXTRA_AXES:
        assert not np.any(np.diff(release[key], axis=0)[off])
    assert np.any(np.diff(release["energy_amount_increment_fmol"], axis=0)[off])
    endpoint = model.STATE_TYPE(*(release[k][-1] for k in model.STATE_TYPE._fields))
    _, p = model.initial_values(parse_spec(fixtures.definition("release")))
    assert np.any(
        np.abs(model.pool_dilution_pJ(endpoint, p) - endpoint.pool_volume_work_pJ) > 1e-12
    )
    evidence(
        "water-pool-accounting",
        dict(
            status="passed",
            diagnostics=errors,
            water_off_keeps_all_water_ledgers_fixed=True,
            pools_continue_during_water_block=True,
            endpoint_dilution_distinct_from_integrated_volume_work=True,
        ),
    )
