"""Conserved joint gate states: independent transport, chemistry, clocks and replay."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import jax
import numpy as np
import pytest
from scipy.linalg import expm

from cells.core.batch import BatchSpec, WorldSpec, parse_batch, run_batch
from cells.core.errors import NumericalError
from cells.core.runner import run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.ensemble import ionic
from cells.io import load_snapshot
from cells.models import surface_mobile_channel as model
from cells.models import surface_mobile_pump as prior
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step, rk4_step
from cells.processes import mobile_channel_gates as gates
from cells.processes import voltage_gates
from cells.processes.electrochemistry import R
from validation.tissue import kv1_reference
from validation.tissue import surface_mobile_channel_fixtures as fixtures
from validation.tissue import surface_mobile_channel_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def evidence(name, value):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def initial(raw=None):
    spec = parse_spec(fixtures.definition(backend=BACKEND) if raw is None else raw)
    state, p = model.initial_values(spec)
    c = control_values(spec, [0.0])
    return spec, state, p, type(c)(*(v[0] for v in c))


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
    assert parse_spec(spec.to_dict()) == spec and get_model(spec.model) is model
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_complete_stage_and_accounting(arm, padded):
    raw = fixtures.definition(arm, padded=padded)
    spec, state, p, control = initial(raw)
    actual = model.readouts(state, control, p, xp=np)
    c = reference.bind(raw)
    expected, phi, proof = reference.evaluate(c, reference.initial(c), 0)
    ratio = error_budget(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    np.testing.assert_allclose(
        np.r_[
            actual.pump.field.potential_V[:1],
            actual.pump.field.potential_V[p.active.size : p.active.size + 2],
        ],
        phi,
        atol=3e-13,
        rtol=3e-10,
    )
    assert actual.valid and abs(actual.pump.field.energy_balance_pJ_s) < 1e-10
    assert all(v == 0 for k, v in model.check_values(state, spec).items() if "channel" in k)
    assert np.min(actual.gating.dissipation, initial=0) >= -1e-15
    if arm in ("frozen", "counterflow", "empty"):
        assert not np.any(actual.gating.transfer)
    if arm in ("immobile", "empty"):
        assert not np.any(actual.surface.flux_fmol_s)
    if arm == "counterflow":
        np.testing.assert_allclose(
            actual.derivative.channel_state_amount_increment.sum(axis=1), 0, atol=2e-16, rtol=0
        )
        assert np.max(np.abs(actual.derivative.channel_state_amount_increment)) > 1e-3
    evidence(
        f"channel-mobile-stage-{arm}-{'padded' if padded else 'compact'}",
        dict(status="passed", inputs=raw, max_error_over_budget=ratio, independent_root=proof),
    )


@pytest.mark.parametrize("boundary", ["open", "closed"])
def test_multicell_field_and_absent_population(boundary):
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
    assert actual.valid
    assert not np.any(
        actual.derivative.channel_state_amount_increment[p.channel_state_reference == 0]
    )
    evidence(
        "channel-mobile-multicell-" + boundary,
        dict(status="passed", inputs=raw, max_error_over_budget=ratio, independent_root=proof),
    )


@pytest.mark.parametrize("voltage", [-0.10, -0.04, 0.03])
@pytest.mark.parametrize("correlated", [False, True])
def test_fixed_voltage_joint_generator_and_mixing_identity(voltage, correlated):
    y = 0.01 * np.asarray((0.4, 0.1, 0.1, 0.4) if correlated else fixtures.factorized(0.3, 0.7))
    target, tau = kv1_reference.kinetics(voltage, 5)
    alpha = [float(t / s) for t, s in zip(target, tau, strict=True)]
    beta = [float((1 - t) / s) for t, s in zip(target, tau, strict=True)]
    matrix = np.zeros((4, 4))
    for source, dest, gate in reference.TRANSITIONS:
        matrix[dest, source] += alpha[gate]
        matrix[source, source] -= alpha[gate]
        matrix[source, dest] += beta[gate]
        matrix[dest, dest] -= beta[gate]

    def rates(v):
        return gates.rates(
            v.reshape((1, 4, 1)),
            np.array([[voltage]]),
            np.ones((1, 1), dtype=bool),
            np.ones(1, dtype=bool),
            298.15,
            xp=np,
        )

    start = rates(y)
    np.testing.assert_allclose(start.amount_rate.ravel(), matrix @ y, rtol=3e-13, atol=2e-15)
    mixing_rate = 1e-3 * R * 298.15 * np.sum(np.log(y) * start.amount_rate.ravel())
    assert abs(mixing_rate + start.dissipation.sum() - start.bias_work.sum()) < 2e-13
    assert start.valid and np.min(start.dissipation) >= 0
    state = y.copy()
    for _ in range(32):
        state = rk4_step(lambda v: rates(v).amount_rate.ravel(), state, 1.25e-5)
    expected = expm(matrix * 0.0004) @ y
    np.testing.assert_allclose(state, expected, atol=3e-14, rtol=3e-12)
    target, tau = voltage_gates.kinetics(np.asarray([voltage]), xp=np)
    m, h = (y[2] + y[3]) / y.sum(), (y[1] + y[3]) / y.sum()
    d = start.amount_rate.ravel()
    np.testing.assert_allclose(
        [(d[2] + d[3]) / y.sum(), (d[1] + d[3]) / y.sum()],
        (target[:, 0] - [m, h]) / tau[:, 0],
        atol=1e-13,
        rtol=3e-13,
    )
    evidence(
        f"channel-mobile-generator-{voltage}-{'correlated' if correlated else 'factorized'}",
        dict(
            status="passed",
            voltage_V=voltage,
            correlated=correlated,
            matrix=matrix.tolist(),
            initial=y.tolist(),
            expected=expected.tolist(),
        ),
    )


def test_current_joint_distribution_changes_opening_at_fixed_gate_marginals():
    _, state, p, control = initial()
    original = model.readouts(state, control, p, xp=np)
    delta = state.channel_state_amount_increment.copy()
    delta[0, :, 0] = np.asarray([1, -1, -1, 1]) * 1e-4
    changed = state._replace(channel_state_amount_increment=delta)
    before = model.amounts(state, p)[0, :, 0]
    after = model.amounts(changed, p)[0, :, 0]
    np.testing.assert_allclose(
        [before.sum(), before[2] + before[3], before[1] + before[3]],
        [after.sum(), after[2] + after[3], after[1] + after[3]],
        atol=1e-17,
        rtol=0,
    )
    actual = model.readouts(changed, control, p, xp=np)
    assert abs(actual.permeability[1, 0] - original.permeability[1, 0]) > 1e-11
    off = model.readouts(
        changed, control._replace(channel=np.zeros_like(control.channel)), p, xp=np
    )
    exact(
        (actual.gating.amount_rate, actual.surface.flux_fmol_s),
        (off.gating.amount_rate, off.surface.flux_fmol_s),
    )
    evidence(
        "channel-mobile-correlations",
        dict(
            status="passed",
            same_marginals=True,
            permeability_difference_m_s=float(
                actual.permeability[1, 0] - original.permeability[1, 0]
            ),
            blocking_preserves_gate_and_motion_rates=True,
        ),
    )


def test_empty_blocked_and_zero_permeability_reduce_to_pump_model():
    from cells.core.surface_mobile_pump_spec import Control

    for arm in ("empty", "blocked", "zero_permeability"):
        _, state, p, c = initial(fixtures.definition(arm))
        actual = model.readouts(state, c, p, xp=np).derivative
        expected = prior.rhs(
            model.prior_state(state),
            Control(c.membrane, c.junction, c.pump),
            model.prior_layout(p),
            p.active,
            xp=np,
        )
        exact(model.prior_state(actual), expected)


def test_channel_events_and_empty_surface_graph():
    spec, _, _, _ = initial(fixtures.definition("release"))
    assert 0.000137 in timeline(spec) and 0.000237 in timeline(spec)
    c = control_values(spec, [0.000137 - 1e-10, 0.000137, 0.000237])
    assert (
        not np.any(c.channel[0]) and np.all(c.channel[1, :2, :2] > 0) and not np.any(c.channel[2])
    )
    raw = fixtures.definition()
    raw["model"]["surface_edges"] = []
    raw["execution"]["surface_edge_capacity"] = 0
    _, state, p, c = initial(raw)
    assert model.readouts(state, c, p, xp=np).valid
    evidence(
        "channel-mobile-clocks",
        dict(
            status="passed", inputs=spec.to_dict(), times=timeline(spec).tolist(), empty_graph=True
        ),
    )


@pytest.mark.parametrize("name", tuple(model.EXTRA_AXES))
def test_corrupt_state_and_ledgers_rejected(name):
    spec, state, _, _ = initial()
    value = getattr(state, name).copy()
    value[0, 0, 0] += 1e-4
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{name: value}), spec)


@pytest.mark.parametrize(
    "fault",
    [
        "law",
        "charge",
        "species",
        "partial_empty",
        "missing_state",
        "negative",
        "gate_mode",
        "density",
        "duplicate",
        "missing_control",
        "duplicate_control",
        "control_value",
        "control_clock",
        "capacity",
        "step",
        "temperature",
    ],
)
def test_invalid_definitions_rejected(fault):
    raw = fixtures.definition()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    p = m["mobile_channels"][0]
    if fault == "law":
        p["kinetic_law"] = "betse_kir2p1_mh2@1"
    elif fault == "charge":
        p["effective_charge_e"] = 1
    elif fault == "species":
        p["species_id"] = "Na"
    elif fault == "partial_empty":
        p["initial_state_amount_fmol"]["m0h0"]["patch_0"] = 0
    elif fault == "missing_state":
        del p["initial_state_amount_fmol"]["m1h1"]
    elif fault == "negative":
        p["initial_state_amount_fmol"]["m0h0"]["patch_0"] = -1
    elif fault == "gate_mode":
        p["gate_mode"] = "reset_on_arrival"
    elif fault == "density":
        p["reference_density_fmol_per_um2"] = 0
    elif fault == "duplicate":
        p["id"] = m["mobile_pumps"][0]["id"]
    elif fault == "missing_control":
        e["channel_controls"].pop()
    elif fault == "duplicate_control":
        e["channel_controls"].append(copy.deepcopy(e["channel_controls"][0]))
    elif fault == "control_value":
        e["channel_controls"][0]["schedule"][0]["availability"] = 1.01
    elif fault == "control_clock":
        e["channel_controls"][0]["schedule"][0]["time"] = 1e-4
    elif fault == "capacity":
        x["channel_population_capacity"] = 1
    elif fault == "step":
        p["diffusivity_um2_per_s"] *= 100
    else:
        m["temperature_K"] = 300
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


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
    bad = control._replace(channel=control.channel.at[0, 0].set(-1.0))
    kept, valid = step(state, bad)
    assert not valid
    exact(kept, state)
    bad_state = state._replace(
        channel_state_amount_increment=state.channel_state_amount_increment.at[0, 0, 0].set(-1.0)
    )
    kept, valid = step(bad_state, control)
    assert not valid
    exact(kept, bad_state)
    evidence(
        "channel-mobile-compiled-guard",
        dict(status="passed", backend=BACKEND, complete_rejection=True),
    )


@pytest.fixture(scope="module")
def trajectories():
    values = {}
    for arm in ("mobile", "immobile", "blocked", "counterflow", "release"):
        v = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
        assert all(y.device.platform == BACKEND for y in v.final.state)
        values[arm] = v
        if EVIDENCE:
            path = Path(EVIDENCE) / BACKEND
            path.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                path / ("channel-mobile-trajectory-" + arm + ".npz"),
                **{k: np.asarray(y) for k, y in v.history._asdict().items()},
                **{"observed_" + k: y for k, y in vars(v.observations).items()},
            )
    return values


@pytest.mark.parametrize("arm", ["mobile", "immobile", "blocked", "counterflow", "release"])
def test_complete_trajectory_against_independent_reference(arm, trajectories):
    v = trajectories[arm]
    expected = reference.integrate(v.spec.to_dict())
    c = reference.bind(v.spec.to_dict())
    evidence(
        "channel-mobile-reference-" + arm,
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
        "channel-mobile-trajectory-" + arm,
        dict(
            status="passed",
            inputs=v.spec.to_dict(),
            max_error_over_budget=ratio,
            diagnostics=v.diagnostics,
        ),
    )


def test_analytic_diffusion_correlations_and_transport_effect(trajectories):
    v = trajectories["mobile"]
    p = v.final.layout
    for k, pop in enumerate(v.spec.model.mobile_channels):
        a, b = p.mobile_patch_area_um2[:2]
        start = p.channel_state_reference[k, :, :2].sum(axis=0)
        eq = np.sum(start) * np.asarray([a, b]) / (a + b)
        decay = pop.diffusivity_um2_per_s * 2 * (1 / a + 1 / b)
        target = eq[None] + (start - eq)[None] * np.exp(-decay * v.observations.times[:, None])
        np.testing.assert_allclose(
            v.observations.channel_state_amount_fmol[:, k, :, :2].sum(axis=1),
            target,
            atol=3e-13,
            rtol=0,
        )
    c = trajectories["counterflow"]
    p = c.final.layout
    for k, pop in enumerate(c.spec.model.mobile_channels):
        a, b = p.mobile_patch_area_um2[:2]
        start = p.channel_state_reference[k, :, :2]
        eq = start.sum(axis=1)[:, None] * np.asarray([a, b])[None] / (a + b)
        target = eq[None] + (start - eq)[None] * np.exp(
            -pop.diffusivity_um2_per_s * 2 * (1 / a + 1 / b) * c.observations.times[:, None, None]
        )
        np.testing.assert_allclose(
            c.observations.channel_state_amount_fmol[:, k, :, :2], target, atol=3e-13, rtol=0
        )
    assert not np.any(c.history.channel_gate_transferred)
    assert not np.any(trajectories["immobile"].history.channel_state_transferred)
    assert np.max(np.abs(v.observations.channel_joint_correlation[-1])) > 1e-4
    voltage = float(
        np.max(
            np.abs(
                v.observations.membrane_voltage_V[-1]
                - trajectories["immobile"].observations.membrane_voltage_V[-1]
            )
        )
    )
    flux = float(
        np.max(
            np.abs(
                v.observations.membrane_flux_fmol_s[-1]
                - trajectories["immobile"].observations.membrane_flux_fmol_s[-1]
            )
        )
    )
    assert voltage > 1e-9 and flux > 1e-5
    evidence(
        "channel-mobile-coupling",
        dict(
            status="passed",
            voltage_difference_V=voltage,
            flux_difference_fmol_s=flux,
            max_joint_correlation=float(
                np.max(np.abs(v.observations.channel_joint_correlation[-1]))
            ),
            counterflow_conformation_analytic=True,
            scope="synthetic controls, not biological cases",
        ),
    )


@pytest.mark.parametrize("arm", ["mobile", "counterflow", "release"])
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
        "channel-mobile-refinement-" + arm,
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
    # Sequential simulation workers avoid overlapping compiled graph inventories.
    commands = (
        (
            "prepare",
            [
                sys.executable,
                "-B",
                "-m",
                "validation.tissue.surface_mobile_channel_replay",
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
        "channel-mobile-replay",
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
    raw["worlds"][1]["simulation"]["execution"]["channel_population_capacity"] += 1
    with pytest.raises(ConfigError):
        parse_batch(raw)
    evidence(
        "channel-mobile-worlds",
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
            Path(EVIDENCE) / "cpu" / ("channel-mobile-trajectory-" + arm + ".npz"),
            allow_pickle=False,
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
        "channel-mobile-cpu-gpu",
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
