"""Active ionic transport and water: complete shared-stage and trajectory checks."""

import json
import os
from functools import lru_cache
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly.engine import device_for
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.core.surface_water_kinetic_spec import prior_spec, water_spec
from cells.ensemble import ionic
from cells.models import surface_kinetic as prior
from cells.models import surface_tissue as passive
from cells.models import surface_water as passive_water
from cells.models import surface_water_kinetic as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step
from tests.unit.test_surface_repair_full import compare_backend
from tests.unit.test_surface_tissue import exact
from validation.tissue import surface_water_kinetic_fixtures as fixtures
from validation.tissue import surface_water_kinetic_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
PUBLISHED = os.environ.get("CELLS_COMPONENT_PUBLISHED_EVIDENCE")
PREFIX = "active-water"


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


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_registered_complete_state_and_ensemble(backend):
    raw = fixtures.definition("release", backend=backend)
    spec, state, p, _ = initial(raw)
    assert len(state) == 23 and get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    assert model.check_values(state, spec)["max_global_water_balance_error_pL"] == 0
    evidence(
        "registration-" + backend,
        dict(status="passed", state_fields=list(state._fields), inputs=spec.to_dict()),
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_stage_with_shared_ions_and_current_volumes(arm, padded):
    time = 32e-6 if arm == "release" else 0.0
    raw = fixtures.definition(arm, padded=padded)
    spec, state, p, control = initial(raw, time=time)
    # Nonzero volume history tests concentration ownership beyond initial values.
    if arm != "sealed":
        state.volume_increment_pL[0] = 0.01
        state.extracellular_volume_increment_pL[0] = -0.01
        state.water_transferred_pL[0] = -0.01
    before = tuple(v.copy() for v in state)
    c = reference.bind(spec.to_dict())
    actual = model.rhs(state, control, p, p.active, xp=np)
    expected, phi, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), time)
    ratio = error_budget(
        c,
        reference.flatten(c, actual._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    f = model.field_values(state, control, p, xp=np)
    np.testing.assert_allclose(
        np.r_[f.potential_V[:1], f.potential_V[p.active.size : p.active.size + 1]],
        phi,
        rtol=3e-10,
        atol=3e-11,
    )
    exact(state, before)
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    assert abs(model.water_values(state, control, p, xp=np).energy_balance_pJ_s) < 1e-9
    evidence(
        f"stage-{arm}-{int(padded)}",
        dict(status="passed", inputs=spec.to_dict(), max_error_over_budget=ratio),
    )


def test_multicell_shared_outside_owners_and_full_field_reference():
    raw = fixtures.multicell()
    raw["model"]["species"].reverse()
    spec, state, p, control = initial(raw)
    c = reference.bind(spec.to_dict())
    actual = model.rhs(state, control, p, p.active, xp=np)
    expected, _, proof = reference.evaluate(c, reference.initial(c), 0.0)
    ratio = error_budget(
        c,
        reference.flatten(c, actual._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert (
        abs(np.sum(actual.volume_increment_pL) + np.sum(actual.extracellular_volume_increment_pL))
        < 2e-15
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    evidence("multicell", dict(status="passed", max_error_over_budget=ratio, inputs=spec.to_dict()))


def test_sealed_water_reduces_exactly_to_existing_ionic_stage():
    spec, state, p, control = initial(fixtures.definition("sealed"))
    actual = model.rhs(state, control, p, p.active, xp=np)
    original = prior_spec(spec)
    old, q = prior.initial_values(original)
    ctl = control_values(original, [0.0])
    expected = prior.rhs(old, type(ctl)(*(v[0] for v in ctl)), q, q.active, xp=np)
    exact(model.prior_state(actual), expected)
    for name in model.EXTRA_AXES:
        assert np.all(getattr(actual, name) == 0)
    evidence("sealed-reduction", dict(status="passed", original_fields=19, water_fields=4))


def test_absent_active_routes_reduce_to_passive_water():
    spec, state, p, control = initial(fixtures.definition("passive"))
    projected = water_spec(spec)
    old, q = passive_water.initial_values(projected)
    table = control_values(projected, [0.0])
    expected = passive_water.rhs(old, type(table)(*(v[0] for v in table)), q, q.active, xp=np)
    actual = model.rhs(state, control, p, p.active, xp=np)
    exact(model.water_state(actual), expected)
    for name in set(prior.STATE_TYPE._fields) - set(passive.STATE_TYPE._fields):
        assert not np.any(getattr(actual, name))
    evidence("passive-reduction", dict(status="passed", complete_passive_water_fields=16))


def test_ensemble_readout_rejects_invalid_volume():
    spec, state, p, _ = initial()
    state.volume_increment_pL[0] = p.water_minimum_volume_pL[0] - p.volume[0]
    with pytest.raises(NumericalError, match="outside domain"):
        model.ensemble_voltage(state, p, spec, 0.0)


@pytest.mark.parametrize("name", model.STATE_TYPE._fields)
def test_corrupt_complete_ledgers_are_rejected(name):
    spec, state, _, _ = initial()
    getattr(state, name).flat[0] = (
        2.0 if name.endswith("_gate") else 1e-15 if name.endswith("_C") else 1e-5
    )
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


def test_compiled_rejection_keeps_every_field_unchanged():
    jax.config.update("jax_enable_x64", True)
    _, state, p, control = initial(fixtures.definition("coupled"))
    device = device_for(BACKEND, 0)
    state, control, p = jax.device_put((state, control, p), device)
    step = jax.jit(
        lambda s, ctl, q, dt: rk4_checked_step(
            model.rhs, model.domain_valid, s, dt, ctl, q, q.active
        )
    )
    accepted, valid = step(state, control, p, np.float64(1e-4))
    assert bool(valid) and np.any(np.asarray(accepted.volume_increment_pL))
    for dt, ctl in ((100.0, control), (1e-4, control._replace(water=control.water * np.nan))):
        rejected, valid = step(state, ctl, p, np.float64(dt))
        assert not bool(valid)
        exact(rejected, state)
    evidence(
        "compiled-guard", dict(status="passed", backend=BACKEND, rejected_trials_preserved=True)
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
    raise AssertionError("Require saved water evidence: " + name + "/" + backend)


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
        value.observations.cell_potential_V[:, :1],
        value.observations.extracellular_potential_V[:, :1],
    ]
    np.testing.assert_allclose(phi, expected["potential_V"], rtol=3e-9, atol=2e-8)
    stable = None
    if arm == "release":
        tighter = independent(arm, raw, refinement=4)
        stable = error_budget(
            c, expected["state"], tighter["state"], atol=3e-14, charge_atol=3e-28, rtol=3e-11
        )
    assert value.diagnostics["max_energy_balance_error_pJ"] <= passive.ENERGY_ATOL_PJ
    assert value.diagnostics["max_global_water_balance_error_pL"] <= model.VOLUME_ATOL_PL
    evidence(
        "trajectory-" + arm,
        dict(
            status="passed",
            inputs=fixtures.normalized(raw),
            max_error_over_budget=ratio,
            reference_stability_over_budget=stable,
            complete_fields=23,
            diagnostics=value.diagnostics,
        ),
    )


def test_saved_physical_controls_and_dilution():
    results = {}
    for arm in fixtures.ARMS:
        receipt, data = saved("history-" + arm)
        assert receipt["inputs"] == fixtures.normalized(
            parse_spec(fixtures.definition(arm)).to_dict()
        )
        results[arm] = data
    coupled, sealed = results["coupled"], results["sealed"]
    assert coupled["volume_increment_pL"][-1, 0] > 0
    for field in model.EXTRA_AXES:
        assert not np.any(sealed[field])
    assert coupled["pump_cycles"][-1, 0] > 0
    assert results["reverse"]["pump_cycles"][-1, 0] < 0
    for field in ("pump_cycles", "pump_dissipated_energy_pJ", "metabolic_work_pJ"):
        assert not np.any(results["inhibited"][field])
        assert not np.any(results["passive"][field])
    assert not np.any(results["passive"]["channel_transferred"])
    assert coupled["pump_cycles"][-1, 0] != sealed["pump_cycles"][-1, 0]
    assert not np.array_equal(
        coupled["observed_membrane_voltage_V"], sealed["observed_membrane_voltage_V"]
    )
    release = results["release"]
    times = release["observed_times"]
    assert not np.any(release["observed_water_flow_pL_s"][(times >= 13.3e-6) & (times < 31.1e-6)])
    assert not np.any(
        release["observed_pump_cycle_rate_fmol_s"][(times >= 23.7e-6) & (times < 41.3e-6)]
    )
    assert not np.any(
        release["observed_channel_flux_fmol_s"][(times >= 17.3e-6) & (times < 37.1e-6)]
    )
    assert np.any(release["observed_water_flow_pL_s"][times == 31.1e-6])
    # The source is maintained, so current concentrations affect pumping while
    # the ATP free energy per cycle remains a fixed, separately recorded input.
    evidence(
        "controls",
        dict(
            status="passed",
            water_feedback_on_pump=True,
            water_feedback_on_voltage=True,
            reverse_cycles=True,
            independent_clocks=True,
            synthetic=True,
            finite_atp=False,
        ),
    )


def test_three_grid_refinement():
    _, base = saved("history-release")
    raw = fixtures.definition("release", backend=BACKEND)
    c = reference.bind(raw)
    _, target = saved("reference-release-r4", "cpu")
    errors, ratios = [], []
    for i, dt in enumerate(fixtures.STEPS):
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
            steps_s=fixtures.STEPS,
            max_absolute_errors=errors,
            max_error_over_budget=ratios,
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
