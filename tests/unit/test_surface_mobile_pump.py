"""Owned mobile ATPase: independent kinetics, conservation, clocks and replay."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch, run_batch
from cells.core.errors import NumericalError
from cells.core.runner import run, timeline
from cells.core.schedule import SurfaceControl, control_values
from cells.core.specs import ConfigError, parse_spec
from cells.ensemble import ionic
from cells.io import load_snapshot
from cells.models import surface_mobile_pump as model
from cells.models import surface_redistribution as prior
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step, rk4_step
from validation.tissue import surface_mobile_pump_fixtures as fixtures
from validation.tissue import surface_mobile_pump_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def evidence(name, value):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def initial(raw=None):
    spec = parse_spec(fixtures.definition(backend=BACKEND) if raw is None else raw)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, p, type(controls)(*(v[0] for v in controls))


def exact(a, b):
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)


def error_budget(c, actual, expected, *, atol=2e-11, charge_atol=3e-25, rtol=3e-9):
    absolute = reference.flatten(
        c,
        {
            k: np.full(shape, charge_atol if k.endswith("_C") else atol)
            for k, shape in c["shapes"].items()
        },
    )
    ratio = np.abs(actual - expected) / (absolute + rtol * np.abs(expected))
    assert np.max(ratio, initial=0) <= 1
    return float(np.max(ratio, initial=0))


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_registration_roundtrip_and_ensemble(backend):
    raw = fixtures.definition(backend=backend)
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_stage_ion_and_energy_owners(arm, padded):
    raw = fixtures.definition(arm, padded=padded)
    spec, state, p, control = initial(raw)
    v = model.readouts(state, control, p, xp=np)
    c = reference.bind(raw)
    target, phi, proof = reference.evaluate(c, reference.initial(c), 0)
    ratio = error_budget(
        c,
        reference.flatten(c, v.derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    np.testing.assert_allclose(
        np.r_[v.field.potential_V[:1], v.field.potential_V[p.active.size : p.active.size + 2]],
        phi,
        atol=3e-13,
        rtol=3e-10,
    )
    assert v.valid and abs(v.field.energy_balance_pJ_s) < 1e-10
    assert model.check_values(state, spec)["max_metabolic_work_error_pJ"] == 0
    np.testing.assert_allclose(
        v.capacity, p.pump_turnover * p.pump_amount_reference, rtol=0, atol=0
    )
    if arm == "reverse":
        assert np.all(v.derivative.pump_cycles[:2, :2] < 0)
        assert np.all(v.derivative.metabolic_work_pJ[:2, :2] < 0)
    elif arm in ("mobile", "immobile", "pump_only", "uniform"):
        assert np.all(v.derivative.pump_cycles[:2, :2] > 0)
        assert np.all(v.derivative.metabolic_work_pJ[:2, :2] > 0)
    else:
        assert not np.any(v.derivative.pump_cycles)
    assert np.min(v.derivative.pump_dissipated_energy_pJ, initial=0) >= -1e-15
    if arm in ("empty", "immobile", "uniform"):
        np.testing.assert_allclose(
            v.derivative.pump_surface_amount_increment, 0, atol=1e-16, rtol=0
        )
    evidence(
        f"pump-mobile-stage-{arm}-{'padded' if padded else 'compact'}",
        dict(status="passed", inputs=raw, max_error_over_budget=ratio, independent_root=proof),
    )


def test_current_pump_amount_sets_capacity_and_controls_do_not_remove_protein():
    spec, state, p, control = initial()
    delta = state.pump_surface_amount_increment.copy()
    delta[0, :2] = [-0.0001, 0.0001]
    changed = state._replace(pump_surface_amount_increment=delta)
    target = reference.bind(spec.to_dict())
    expected, _, _ = reference.evaluate(target, reference.flatten(target, changed._asdict()), 0)
    v = model.readouts(changed, control, p, xp=np)
    error_budget(
        target,
        reference.flatten(target, v.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    start = model.readouts(state, control, p, xp=np)
    np.testing.assert_allclose(
        v.capacity - start.capacity, p.pump_turnover * delta, atol=1e-17, rtol=1e-14
    )
    off = model.readouts(changed, control._replace(pump=np.zeros_like(control.pump)), p, xp=np)
    assert not np.any(off.derivative.pump_cycles)
    np.testing.assert_array_equal(
        v.derivative.pump_surface_amount_increment, off.derivative.pump_surface_amount_increment
    )
    # Block passive pores independently; Na/K pump remains an active route.
    blocked = model.readouts(
        changed, control._replace(membrane=np.zeros_like(control.membrane)), p, xp=np
    )
    assert np.max(np.abs(blocked.derivative.pump_cycles)) > 0
    assert not np.any(blocked.derivative.membrane_transferred)


@pytest.mark.parametrize("boundary", ["open", "closed"])
def test_multicell_resolved_field_and_absent_population(boundary):
    raw = fixtures.multicell(boundary)
    _, state, p, control = initial(raw)
    actual = model.readouts(state, control, p, xp=np)
    c = reference.bind(raw)
    expected, _, proof = reference.evaluate(c, reference.initial(c), 0)
    ratio = error_budget(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert actual.valid and abs(actual.field.energy_balance_pJ_s) < 1e-10
    absent = p.pump_amount_reference == 0
    assert not np.any(actual.derivative.pump_cycles[absent])
    assert not np.any(actual.derivative.pump_surface_amount_increment[absent])
    evidence(
        "pump-mobile-multicell-" + boundary,
        dict(status="passed", inputs=raw, max_error_over_budget=ratio, independent_root=proof),
    )


def test_unequal_patch_areas_do_not_scale_turnover_twice():
    _, state, p, control = initial()
    neutral_control = control._replace(
        pump=np.ones_like(control.pump) * p.pump_active[:, None] * p.membrane_active
    )
    v = model.readouts(state, neutral_control, p, xp=np)
    # Each pump molecule has the same turnover coefficient on unequal areas.
    np.testing.assert_allclose(
        v.capacity[0, :2] / p.pump_amount_reference[0, :2], 25.0, atol=0, rtol=0
    )
    np.testing.assert_allclose(
        v.capacity[1, :2] / p.pump_amount_reference[1, :2], 9.0, atol=0, rtol=0
    )


@pytest.mark.parametrize(
    "fault",
    [
        "charge",
        "law",
        "stoichiometry",
        "role",
        "metabolism",
        "turnover",
        "partial_empty",
        "missing_patch",
        "duplicate",
        "missing_control",
        "duplicate_control",
        "unknown_patch",
        "control_value",
        "control_clock",
        "capacity",
        "step",
        "temperature",
    ],
)
def test_bad_definitions_rejected(fault):
    raw = fixtures.definition()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    p = m["mobile_pumps"][0]
    if fault == "charge":
        p["effective_charge_e"] = 1
    elif fault == "law":
        p["law"] = "synthetic_drive"
    elif fault == "stoichiometry":
        p["stoichiometry"]["Na"] = -2
    elif fault == "role":
        p["roles"]["sodium"] = "Cl"
    elif fault == "metabolism":
        p["metabolism"]["atp_mM"] = 0
    elif fault == "turnover":
        p["turnover_per_s"] = -1
    elif fault == "partial_empty":
        p["initial_amount_fmol"]["patch_0"] = 0
    elif fault == "missing_patch":
        del p["initial_amount_fmol"]["patch_1"]
    elif fault == "duplicate":
        p["id"] = m["mobile_populations"][0]["id"]
    elif fault == "missing_control":
        e["pump_controls"].pop()
    elif fault == "duplicate_control":
        e["pump_controls"].append(copy.deepcopy(e["pump_controls"][0]))
    elif fault == "unknown_patch":
        e["pump_controls"][0]["membrane_id"] = "missing"
    elif fault == "control_value":
        e["pump_controls"][0]["schedule"][0]["availability"] = 1.01
    elif fault == "control_clock":
        e["pump_controls"][0]["schedule"][0]["time"] = 0.0001
    elif fault == "capacity":
        x["pump_population_capacity"] = 1
    elif fault == "step":
        p["diffusivity_um2_per_s"] *= 100
    else:
        m["temperature_K"] = 500
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


@pytest.mark.parametrize("name", tuple(model.EXTRA_AXES))
def test_corrupt_pump_material_cycle_and_energy_ledgers_rejected(name):
    spec, state, _, _ = initial()
    v = getattr(state, name).copy()
    v[0, 0] += 1e-4
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{name: v}), spec)


def test_empty_inhibited_and_no_turnover_reduce_to_prior_ionic_model():
    for arm in ("empty", "inhibited", "no_turnover"):
        spec, state, p, control = initial(fixtures.definition(arm))
        actual = model.rhs(state, control, p, p.active, xp=np)
        expected = prior.rhs(
            model.prior_state(state),
            SurfaceControl(control.membrane, control.junction),
            model.prior_layout(p),
            p.active,
            xp=np,
        )
        exact(model.prior_state(actual), expected)
        assert not np.any(actual.metabolic_work_pJ)
        if arm != "empty":
            assert np.max(np.abs(actual.pump_surface_amount_increment)) > 0
        assert parse_spec(spec.to_dict()) == spec


def test_pump_only_events_enter_ordinary_grid_and_controls():
    spec, _, _, _ = initial(fixtures.definition("release"))
    grid = timeline(spec)
    assert 0.000137 in grid and 0.000237 in grid
    c = control_values(spec, [0.000137 - 1e-10, 0.000137, 0.000237])
    assert not np.any(c.pump[0]) and np.all(c.pump[1, :2, :2] > 0) and not np.any(c.pump[2])
    assert not np.any(c.pump[:, 2]) and not np.any(c.pump[:, :, 2])
    evidence(
        "pump-mobile-clocks", dict(status="passed", inputs=spec.to_dict(), times=grid.tolist())
    )


def test_compiled_stage_and_invalid_trial_guard():
    _, state, p, control = initial()
    expected = model.rhs(state, control, p, p.active, xp=np)
    state, p, control = jax.device_put((state, p, control), jax.devices(BACKEND)[0])
    actual = jax.jit(model.rhs)(state, control, p, p.active)
    for name, a, b in zip(model.STATE_TYPE._fields, actual, expected, strict=True):
        assert a.device.platform == BACKEND
        np.testing.assert_allclose(a, b, atol=3e-23 if name.endswith("_C") else 3e-12, rtol=3e-10)
    step = jax.jit(
        lambda y, c: rk4_checked_step(model.rhs, model.domain_valid, y, 1.25e-5, c, p, p.active)
    )
    bad = control._replace(pump=control.pump.at[0, 0].set(-1.0))
    kept, valid = step(state, bad)
    assert not valid
    exact(kept, state)
    bad_state = state._replace(
        pump_surface_amount_increment=state.pump_surface_amount_increment.at[0, 0].set(-1.0)
    )
    kept, valid = step(bad_state, control)
    assert not valid
    exact(kept, bad_state)
    evidence(
        "pump-mobile-compiled-guard",
        dict(status="passed", backend=BACKEND, complete_rejection=True),
    )


@pytest.fixture(scope="module")
def trajectories():
    values = {}
    for arm in ("mobile", "immobile", "inhibited", "reverse", "release"):
        v = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
        assert all(y.device.platform == BACKEND for y in v.final.state)
        values[arm] = v
        if EVIDENCE:
            path = Path(EVIDENCE) / BACKEND
            path.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                path / ("pump-mobile-trajectory-" + arm + ".npz"),
                **{k: np.asarray(y) for k, y in v.history._asdict().items()},
                **{"observed_" + k: y for k, y in vars(v.observations).items()},
            )
    return values


@pytest.mark.parametrize("arm", ["mobile", "immobile", "inhibited", "reverse", "release"])
def test_complete_trajectory_against_independent_reference(arm, trajectories):
    v = trajectories[arm]
    expected = reference.integrate(v.spec.to_dict())
    c = reference.bind(v.spec.to_dict())
    evidence(
        "pump-mobile-reference-" + arm,
        dict(status="evaluated", inputs=v.spec.to_dict(), reference=expected),
    )
    ratio = error_budget(
        c, reference.flatten(c, vars(v.observations)), np.asarray(expected["state"])
    )
    np.testing.assert_allclose(
        np.c_[
            v.observations.cell_potential_V[:, :1], v.observations.extracellular_potential_V[:, :2]
        ],
        expected["potential_V"],
        atol=2e-8,
        rtol=3e-9,
    )
    evidence(
        "pump-mobile-trajectory-" + arm,
        dict(
            status="passed",
            inputs=v.spec.to_dict(),
            max_error_over_budget=ratio,
            diagnostics=v.diagnostics,
        ),
    )


def test_analytic_pump_diffusion_and_transport_effect(trajectories):
    v = trajectories["mobile"]
    p = v.final.layout
    for k, pop in enumerate(v.spec.model.mobile_pumps):
        a, b = p.mobile_patch_area_um2[:2]
        start = p.pump_amount_reference[k, :2]
        equilibrium = np.sum(start) * np.asarray([a, b]) / (a + b)
        decay = pop.diffusivity_um2_per_s * 2 * (1 / a + 1 / b)
        expected = equilibrium[None] + (start - equilibrium)[None] * np.exp(
            -decay * v.observations.times[:, None]
        )
        np.testing.assert_allclose(
            v.observations.pump_amount_fmol[:, k, :2], expected, atol=3e-13, rtol=0
        )
    np.testing.assert_array_equal(
        v.history.pump_surface_amount_increment,
        trajectories["inhibited"].history.pump_surface_amount_increment,
    )
    assert not np.any(trajectories["immobile"].history.pump_surface_amount_increment)
    assert not np.any(trajectories["inhibited"].history.pump_cycles)
    flux = float(
        np.max(
            np.abs(
                v.observations.pump_cycle_rate_fmol_s[-1]
                - trajectories["immobile"].observations.pump_cycle_rate_fmol_s[-1]
            )
        )
    )
    voltage = float(
        np.max(
            np.abs(
                v.observations.membrane_voltage_V[-1]
                - trajectories["immobile"].observations.membrane_voltage_V[-1]
            )
        )
    )
    assert flux > 1e-5 and voltage > 1e-9
    evidence(
        "pump-mobile-coupling",
        dict(
            status="passed",
            pump_cycle_difference_fmol_s=flux,
            voltage_difference_V=voltage,
            scope="synthetic controls, not biological timescales",
        ),
    )


@pytest.mark.parametrize("arm", ["mobile", "reverse", "release"])
def test_numpy_refinement_and_reference_accuracy(arm):
    raw = fixtures.definition(arm)
    c = reference.bind(raw)
    target = np.asarray(reference.integrate(raw)["state"])[-1]
    tighter = np.asarray(reference.integrate(raw, refinement=2)["state"])[-1]
    stable = error_budget(c, target, tighter, atol=2e-13, charge_atol=3e-27, rtol=0)
    errors, charges = [], []
    steps = [1.25e-5, 6.25e-6, 3.125e-6]
    for dt in steps:
        candidate = copy.deepcopy(raw)
        candidate["execution"]["dt"] = dt
        spec, state, p, _ = initial(candidate)
        grid = timeline(spec)
        controls = control_values(spec, grid[:-1])
        for i, h in enumerate(np.diff(grid)):
            control = type(controls)(*(v[i] for v in controls))
            state = rk4_step(
                lambda y, held=control, layout=p: model.rhs(y, held, layout, layout.active, xp=np),
                state,
                h,
            )
            assert model.control_domain_valid(state, control, p, p.active, xp=np)
        diff = reference.unpack(c, reference.flatten(c, state._asdict()) - tighter)
        errors.append(
            max(
                float(np.max(np.abs(v), initial=0)) for k, v in diff.items() if not k.endswith("_C")
            )
        )
        charges.append(float(np.max(np.abs(diff["electrode_charge_transferred_C"]), initial=0)))
    assert errors[-1] <= max(errors[0] / 100, 3e-13)
    assert charges[-1] <= max(charges[0] / 100, 3e-27)
    evidence(
        "pump-mobile-refinement-" + arm,
        dict(
            status="passed",
            steps_s=steps,
            amount_energy_max_errors=errors,
            electrode_charge_max_errors_C=charges,
            reference_tightening_error_over_budget=stable,
            implementation="NumPy production RK4/RHS",
        ),
    )


def test_complete_saved_restart_branch_and_windows(tmp_path):
    # No trajectories fixture: keep this coordinator free of compiled graphs.
    # Both children inherit the existing process group and its resource guard.
    commands = (
        (
            "prepare",
            [
                sys.executable,
                "-B",
                "-m",
                "validation.tissue.surface_mobile_pump_replay",
                str(tmp_path),
                "--backend",
                BACKEND,
            ],
            480,
        ),
        (
            "fresh",
            [
                sys.executable,
                "-B",
                "-m",
                "cells",
                "resume",
                str(tmp_path / "checkpoint"),
                "--output",
                str(tmp_path / "fresh"),
            ],
            240,
        ),
    )
    for name, command, timeout in commands:
        with (
            (tmp_path / (name + ".stdout.log")).open("x") as out,
            (tmp_path / (name + ".stderr.log")).open("x") as err,
        ):
            subprocess.run(command, stdout=out, stderr=err, timeout=timeout, check=True)
    prepared = json.loads((tmp_path / "prepared.json").read_text())
    assert prepared["status"] == "prepared" and prepared["backend"] == BACKEND
    assert prepared["state_fields"] == list(model.STATE_TYPE._fields)
    assert all(prepared[k] for k in ("disk", "branch", "terminal", "windows"))
    expected = load_snapshot(tmp_path / "expected").checkpoint
    actual = load_snapshot(tmp_path / "fresh/checkpoint_final").checkpoint
    exact(actual.state, expected.state)
    exact(actual.layout, expected.layout)
    assert (actual.time, actual.step_index, actual.event_index) == (
        expected.time,
        expected.step_index,
        expected.event_index,
    )
    with (
        np.load(tmp_path / "expected_history.npz", allow_pickle=False) as target,
        np.load(tmp_path / "fresh/trajectory.npz", allow_pickle=False) as fresh,
    ):
        assert set(target.files) == {"accepted_times", *model.STATE_TYPE._fields}
        for name in target.files:
            np.testing.assert_array_equal(fresh[name], target[name])
    evidence(
        "pump-mobile-replay",
        prepared
        | dict(
            status="passed",
            fresh_process=True,
            fresh_complete_history=True,
            fresh_layout_and_clock=True,
            sequential_workers=True,
        ),
    )


def test_independent_worlds_order_and_identity(trajectories):
    worlds = tuple(
        WorldSpec(i + 1, trajectories[arm].spec) for i, arm in enumerate(("mobile", "release"))
    )
    spec = BatchSpec(worlds, 2, 256, 2**29)
    values = run_batch(spec)
    reversed_values = run_batch(BatchSpec(tuple(reversed(worlds)), 2, 256, 2**29))
    for identity, v in values.worlds.items():
        exact(v.history, reversed_values.worlds[identity].history)
        source = trajectories["mobile" if identity == 1 else "release"]
        for name, a, b in zip(model.STATE_TYPE._fields, v.history, source.history, strict=True):
            np.testing.assert_allclose(
                a, b, atol=3e-25 if name.endswith("_C") else 3e-12, rtol=3e-10
            )
    raw = spec.to_dict()
    raw["worlds"][1]["simulation"]["execution"]["pump_population_capacity"] += 1
    with pytest.raises(ConfigError):
        parse_batch(raw)
    evidence(
        "pump-mobile-worlds",
        dict(status="passed", worlds=2, reordered="bitwise", independent_clocks=True),
    )


def test_cpu_gpu_complete_histories_and_observations(trajectories):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    count = 0
    for arm, v in trajectories.items():
        actual = {
            **v.history._asdict(),
            **{"observed_" + k: y for k, y in vars(v.observations).items()},
        }
        with np.load(
            Path(EVIDENCE) / "cpu" / ("pump-mobile-trajectory-" + arm + ".npz"), allow_pickle=False
        ) as saved:
            assert set(actual) == set(saved.files)
            for name, y in actual.items():
                if name == "observed_times" or name.endswith("_availability"):
                    np.testing.assert_array_equal(y, saved[name])
                else:
                    atol = (
                        3e-25
                        if name.endswith("_C")
                        else (
                            3e-23
                            if name.endswith("_A")
                            else (3e-11 if name.endswith("_V") else 3e-13)
                        )
                    )
                    np.testing.assert_allclose(y, saved[name], rtol=3e-10, atol=atol)
                count += y.size
    evidence(
        "pump-mobile-cpu-gpu",
        dict(
            status="passed",
            physical_scalars=count,
            rtol=3e-10,
            amount_energy_atol=3e-13,
            charge_atol_C=3e-25,
            current_atol_A=3e-23,
            voltage_atol_V=3e-11,
        ),
    )
