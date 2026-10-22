"""Mixed Kv1.5/Kir2.1 laws, resolved coupling and ordinary CPU/GPU execution."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, plan_batch, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble import ionic
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_channels
from cells.models import surface_kinetic as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step
from cells.processes import potassium_channels as channels
from tests.unit import test_surface_kinetic as helpers
from validation.tissue import kir_reference
from validation.tissue import surface_channel_fixtures as fixtures
from validation.tissue import surface_kinetic_fixtures as old_fixtures
from validation.tissue import surface_kinetic_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
ARMS = fixtures.ARMS
PREFIX = "resolved-channels"
MODEL_ID = "resolved_tissue@3"
REFINEMENT_STEPS = (25e-6, 12.5e-6, 6.25e-6)
BATCH_STEP_BUDGET = 1024
SOURCE_HASHES = {
    "vg_k.py": "89412aff6163dfe4ccf61afb82418a788ff8e10fbe2ec8cda24c498316b4842f",
    "channelsabc.py": "ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4",
}
exact, assert_states = helpers.exact, helpers.assert_states


def evidence(name, value):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / (PREFIX + "-" + name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n"
        )


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


def test_design_and_rejections():
    for backend in ("cpu", "gpu"):
        raw = fixtures.definition(backend=backend)
        spec = parse_spec(raw)
        assert spec == parse_spec(spec.to_dict())
        assert get_model(spec.model) is surface_channels
        assert spec.to_dict()["model"]["id"] == "resolved_tissue@3"
        assert (
            ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation
            == spec
        )
    faults = []
    for fault in (
        "unknown_law",
        "v2_identity",
        "wrong_species",
        "missing_species",
        "bad_gate",
        "nan_gate",
        "temperature",
        "step",
        "duplicate",
        "capacity",
        "control",
    ):
        raw = fixtures.definition()
        m, e, x = raw["model"], raw["experiment"], raw["execution"]
        ch = m["channels"][1]
        if fault == "unknown_law":
            ch["kinetic_law"] = "unregistered"
        elif fault == "v2_identity":
            m["id"] = "resolved_tissue@2"
        elif fault == "wrong_species":
            ch["species_id"] = "Na"
        elif fault == "missing_species":
            ch["species_id"] = "absent"
        elif fault == "bad_gate":
            ch["initial_gate"][1] = 1.1
        elif fault == "nan_gate":
            ch["initial_gate"][0] = float("nan")
        elif fault == "temperature":
            m["temperature_K"] = 310.0
        elif fault == "step":
            x["dt"] = 50e-6
        elif fault == "duplicate":
            ch["id"] = m["channels"][0]["id"]
        elif fault == "capacity":
            x["channel_capacity"] = 4
        else:
            e["channel_controls"][1]["schedule"][0]["availability"] = -0.1
        with pytest.raises(ConfigError):
            timeline(parse_spec(raw))
        faults.append(fault)
    evidence("design", dict(status="passed", rejected=faults, inputs=fixtures.definition()))


def test_native_laws_and_discrete_clock(tmp_path):
    output = tmp_path / "native.json"
    worker = Path(__file__).resolve().parents[2] / "validation/betse/potassium_native.py"
    process = subprocess.run(
        ["/mnt/workspaces/Cells/venv-betse/bin/python", "-B", str(worker), str(output)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    (tmp_path / "native.stdout.log").write_text(process.stdout)
    (tmp_path / "native.stderr.log").write_text(process.stderr)
    process.check_returncode()
    native = json.loads(output.read_text())
    assert native["version"] == "1.5.0" and native["source_sha256"] == SOURCE_HASHES
    v = np.asarray(native["voltage_V"])
    device, count = jax.devices(BACKEND)[0], 0
    max_error = 0.0
    for code, name in enumerate(("Kv1p5", "Kir2p1")):
        row = native["laws"][name]
        codes = np.full(v.shape, code, dtype=np.int64)
        target, tau = jax.jit(channels.kinetics)(*jax.device_put((v, codes), device))
        assert target.device.platform == BACKEND
        for actual, expected in (
            (target, row["target"]),
            (target, row["initial"]),
            (tau, row["tau_s"]),
        ):
            np.testing.assert_allclose(actual, expected, rtol=5e-14, atol=5e-15)
            count += actual.size
        assert row["powers"] == [1, 1 + code]
        for trace in row["traces"]:
            gates = np.broadcast_to(np.asarray([[0.2], [0.7]]), (2, v.size)).copy()
            for voltage, expected, opening in zip(
                trace["voltages_V"], trace["gates"], trace["opening"], strict=True
            ):
                t, tau = channels.kinetics(np.asarray(voltage), codes, xp=np)
                dt = trace["dt_s"]
                # This reference-only discrete comparison uses BETSE's clock.
                # The resolved model uses continuous kinetics and RK4 instead.
                gates = (gates * tau + dt * t) / (tau + dt)
                np.testing.assert_allclose(gates, expected, rtol=5e-14, atol=5e-15)
                np.testing.assert_allclose(
                    channels.opening(gates, codes, xp=np), opening, rtol=5e-14, atol=5e-15
                )
                max_error = max(max_error, float(np.max(np.abs(gates - expected))))
                count += gates.size + v.size
    evidence(
        "native",
        dict(
            status="passed",
            native=native,
            compared_scalars=count,
            max_gate_error=max_error,
            capture_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
            scope="isolated laws and native gate clock; no native coupled tissue claim",
        ),
    )


def test_continuous_clamps_and_gate_power():
    voltage = np.linspace(-0.120, 0.060, 37)
    target, tau = channels.kir2p1_kinetics(voltage, xp=np)
    for i, v in enumerate(voltage):
        expected = kir_reference.kinetics(float(v))
        np.testing.assert_allclose(
            target[:, i], [float(x) for x in expected[0]], rtol=3e-14, atol=3e-15
        )
        np.testing.assert_allclose(
            tau[:, i], [float(x) for x in expected[1]], rtol=3e-14, atol=3e-15
        )
    gates = np.asarray([[0.2, 0.2], [0.7, 0.7]])
    np.testing.assert_allclose(
        channels.opening(gates, np.asarray([0, 1]), xp=np), [0.14, 0.098], rtol=1e-15
    )
    device = jax.devices(BACKEND)[0]
    initial_gates = np.broadcast_to(np.asarray([[0.2], [0.7]]), target.shape)
    expected = target + (initial_gates - target) * np.exp(-0.002 / tau)
    errors = []
    for dt in (25e-6, 12.5e-6, 6.25e-6):

        def solve(g, v, step_size=dt):
            t, decay = channels.kir2p1_kinetics(v)

            def step(old, unused):
                k1 = (t - old) / decay
                k2 = (t - old - step_size * k1 / 2) / decay
                k3 = (t - old - step_size * k2 / 2) / decay
                k4 = (t - old - step_size * k3) / decay
                return old + step_size * (k1 + 2 * k2 + 2 * k3 + k4) / 6, None

            return jax.lax.scan(step, g, None, length=round(0.002 / step_size))[0]

        actual = jax.jit(solve)(*jax.device_put((initial_gates, voltage), device))
        errors.append(float(np.max(np.abs(actual - expected))))
    assert errors[0] < 1e-8
    assert errors[-1] <= max(errors[0] * 0.02, 2e-14)
    evidence(
        "clamps",
        dict(
            status="passed",
            voltage_range_V=[-0.12, 0.06],
            voltage_count=37,
            dt_s=[25e-6, 12.5e-6, 6.25e-6],
            max_gate_errors=errors,
            reference="70-digit Decimal parameters and analytic exponential",
            h_power=2,
        ),
    )


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_stage_rates(arm, padded):
    raw = fixtures.definition(arm, padded=padded)
    _, state, p, control = initial(raw)
    c = reference.bind(raw)
    expected, phi, proof = reference.evaluate(c, reference.initial(c), 0.0)
    actual = model.readouts(state, control, p, xp=np)
    ratio = assert_states(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    np.testing.assert_allclose(
        np.r_[
            actual.field.potential_V[:2],
            actual.field.potential_V[p.active.size : p.active.size + 5],
        ],
        phi,
        rtol=3e-10,
        atol=3e-13,
    )
    assert actual.valid and abs(actual.field.energy_balance_pJ_s) < 1e-10
    evidence(
        f"stage-{arm}-{'padded' if padded else 'compact'}",
        dict(status="passed", inputs=raw, max_error_over_budget=ratio, independent_root=proof),
    )


def test_blocked_gates_additive_populations_and_guard():
    spec, state, p, control = initial()
    blocked = control._replace(channel=np.zeros_like(control.channel))
    opened, shut = (model.readouts(state, c, p, xp=np) for c in (control, blocked))
    assert not np.any(shut.derivative.channel_transferred)
    assert np.any(shut.derivative.channel_gate)
    exact((opened.derivative.channel_gate,), (shut.derivative.channel_gate,))
    # Independent reference plus a population ablation detects wrong h powers,
    # shared gates, incorrect ownership or a missing second population.
    ablated = control._replace(channel=control.channel.copy())
    ablated.channel[4] = 0
    reduced = model.readouts(state, ablated, p, xp=np)
    delta = opened.derivative.amount_increment - reduced.derivative.amount_increment
    expected = np.zeros_like(delta)
    expected[1, 0] = -opened.derivative.channel_transferred[4]
    np.testing.assert_allclose(delta, expected, rtol=1e-10, atol=3e-14)
    wrong = state._replace(channel_transferred=state.channel_transferred + 0.01)
    with pytest.raises(NumericalError):
        model.check_values(wrong, spec)
    bad = p._replace(channel_laws=np.full_like(p.channel_laws, 17))
    assert not model.domain_valid(state, bad, bad.active, xp=np)
    device = jax.devices(BACKEND)[0]
    y, layout, c = jax.device_put((state, p, control), device)
    compute = jax.jit(
        lambda s, a, dt: rk4_checked_step(
            model.rhs, model.domain_valid, s, dt, a, layout, layout.active
        )
    )
    kept, valid = compute(y, c._replace(channel=c.channel * 0 + 1.1), 25e-6)
    assert not valid
    exact(kept, y)
    kept, valid = compute(y, c, 1e6)
    assert not valid
    exact(kept, y)
    evidence(
        "controls",
        dict(
            status="passed",
            blocked_gates_evolve=True,
            additive_patch=True,
            corrupt_ledger_rejected=True,
            unknown_numeric_law_rejected=True,
            invalid_control_and_trial_keep_full_state=True,
        ),
    )


def test_legacy_v2_and_kv_only_reduction():
    raw = old_fixtures.definition()
    spec, state, p, control = initial(raw)
    assert not hasattr(p, "channel_laws")
    assert spec.to_dict()["model"]["id"] == "resolved_tissue@2"
    raw["model"]["id"] = "resolved_tissue@3"
    raw["execution"]["dt"] = 25e-6
    _, newer, q, c = initial(raw)
    exact(newer, state)
    a, b = model.readouts(state, control, p, xp=np), model.readouts(newer, c, q, xp=np)
    exact(a.derivative, b.derivative)
    exact(jax.tree.leaves(a.field), jax.tree.leaves(b.field))
    evidence(
        "legacy",
        dict(
            status="passed",
            kv_only_stage_comparison="bitwise",
            v2_layout_unchanged=True,
            v2_rejects_kir=True,
        ),
    )


def test_prior_resolved_compositions():
    from tests.unit import test_surface_calcium as calcium

    for arm in ARMS:
        helpers.test_independent_stage_rates_and_accounting(arm, True)
    for arm in calcium.ARMS:
        calcium.test_independent_stage_rates_and_accounting(arm, True)
    evidence(
        "prior-models",
        dict(
            status="passed",
            v2_arms=list(ARMS),
            calcium_arms=list(calcium.ARMS),
            scope="initial independent rates",
        ),
    )


def test_compiled_smoke(tmp_path):
    raw = fixtures.definition("clamped", backend=BACKEND)
    raw["experiment"].update(end_time=50e-6, observation_times=[0.0, 25e-6, 50e-6])
    value = run(parse_spec(raw))
    assert all(v.device.platform == BACKEND for v in value.final.state)
    write_run(tmp_path / "smoke", value)
    loaded = load_snapshot(tmp_path / "smoke/checkpoint_final")
    exact(loaded.checkpoint.state, value.final.state)
    assert loaded.spec == value.spec
    assert model.summarize(value.history, value.diagnostics, value.spec)["model"] == MODEL_ID
    evidence(
        "smoke", dict(status="passed", inputs=value.spec.to_dict(), diagnostics=value.diagnostics)
    )


@pytest.fixture(scope="module")
def trajectories(tmp_path_factory):
    directory = tmp_path_factory.mktemp(PREFIX)
    values = {}
    for arm in ARMS:
        result = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
        assert all(v.device.platform == BACKEND for v in result.final.state)
        write_run(directory / arm, result, checkpoint_times=(0.001,))
        if EVIDENCE:
            path = Path(EVIDENCE) / BACKEND
            path.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                path / (PREFIX + "-trajectory-" + arm + ".npz"),
                **{k: np.asarray(v) for k, v in result.history._asdict().items()},
                **{"observed_" + k: v for k, v in vars(result.observations).items()},
            )
        values[arm] = result
    return values


@pytest.fixture(scope="module")
def references():
    if BACKEND == "gpu" and EVIDENCE:
        result = {}
        for arm in ARMS:
            saved = json.loads(
                (Path(EVIDENCE) / "cpu" / (PREFIX + "-trajectory-" + arm + ".json")).read_text()
            )
            assert saved["status"] == "passed"
            assert saved["inputs"] == parse_spec(fixtures.definition(arm)).to_dict()
            result[arm] = saved["independent_reference"]
        return result
    return {arm: reference.integrate(fixtures.definition(arm)) for arm in ARMS}


@pytest.mark.parametrize("arm", ARMS)
def test_independent_trajectories(arm, trajectories, references):
    value, expected = trajectories[arm], references[arm]
    c = reference.bind(value.spec.to_dict())
    ratio = assert_states(
        c, reference.flatten(c, vars(value.observations)), np.asarray(expected["state"])
    )
    np.testing.assert_allclose(
        np.c_[
            value.observations.cell_potential_V[:, :2],
            value.observations.extracellular_potential_V[:, :5],
        ],
        expected["potential_V"],
        rtol=3e-9,
        atol=2e-8,
    )
    assert value.diagnostics["max_energy_balance_error_pJ"] <= 2e-8
    if arm == "closed":
        assert not np.any(value.history.reservoir_supplied)
        assert not np.any(value.history.electrode_charge_transferred_C)
    if arm == "release":
        before = value.times <= 0.00073
        assert not np.any(value.history.channel_transferred[before])
        assert np.any(value.history.channel_gate[before][-1] != value.history.channel_gate[0])
        assert np.any(value.observations.channel_flux_fmol_s[value.observations.times == 0.00073])
    evidence(
        "trajectory-" + arm,
        dict(
            status="passed",
            inputs=value.spec.to_dict(),
            max_error_over_budget=ratio,
            independent_reference=expected,
            diagnostics=value.diagnostics,
        ),
    )


def refinement_case(trajectories, references, arm):
    raw = trajectories[arm].spec.to_dict()
    c, target = reference.bind(raw), np.asarray(references[arm]["state"])
    errors, charges, rows = [], [], []
    name = "refinement" if arm == "clamped" else "refinement-" + arm

    def record(status, **extra):
        evidence(
            name,
            dict(
                status=status,
                arm=arm,
                dt_s=list(REFINEMENT_STEPS),
                amount_energy_gate_errors=errors,
                charge_errors_C=charges,
                timesteps=rows,
                reference_settings={
                    k: references[arm][k]
                    for k in ("rtol", "amount_energy_gate_atol", "electrode_charge_atol_C")
                },
                **extra,
            ),
        )

    try:
        for index, dt in enumerate(REFINEMENT_STEPS):
            raw["execution"]["dt"] = dt
            result = trajectories[arm] if dt == REFINEMENT_STEPS[0] else run(parse_spec(raw))
            actual = reference.flatten(c, vars(result.observations))
            diff = reference.unpack(c, actual - target)
            errors.append(
                max(
                    float(np.max(np.abs(v), initial=0))
                    for k, v in diff.items()
                    if not k.endswith("_C")
                )
            )
            charges.append(float(np.max(np.abs(diff["electrode_charge_transferred_C"]))))
            fields = {}
            for field, values in diff.items():
                at = np.unravel_index(np.argmax(np.abs(values)), values.shape)
                fields[field] = dict(
                    max_absolute_error=float(np.abs(values[at])),
                    signed_error=float(values[at]),
                    index=[int(i) for i in at],
                )
            rows.append(dict(dt_s=dt, inputs=result.spec.to_dict(), errors_by_field=fields))
            if EVIDENCE:
                directory = Path(EVIDENCE) / BACKEND
                directory.mkdir(parents=True, exist_ok=True)
                filename = f"{PREFIX}-refinement-{arm}-{index}.npz"
                np.savez_compressed(
                    directory / filename,
                    times=result.observations.times,
                    actual_state=actual,
                    expected_state=target,
                )
                rows[-1]["state_artifact"] = filename
                rows[-1]["state_shapes"] = c["shapes"]
            # Retain the values before any accuracy assertion can stop this test.
            record("running")
            assert_states(c, actual, target)
        assert errors[-1] <= max(errors[0] * 0.2, 3e-13)
        assert charges[-1] <= max(charges[0] * 0.2, 3e-27)
    except Exception as error:
        record("failed", error=repr(error))
        raise
    record("passed")


def test_refinement(trajectories, references):
    refinement_case(trajectories, references, "clamped")


def test_restart_branch_windows_and_identity(trajectories, tmp_path):
    value = trajectories["clamped"]
    checkpoint = value.checkpoint_at(0.001)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    exact(loaded.checkpoint.state, checkpoint.state)
    resumed = run(loaded.spec, loaded.checkpoint)
    exact(resumed.history, tuple(v[checkpoint.step_index :] for v in value.history))
    exact(tuple(v[0] for v in run(value.spec, value.final).history), value.final.state)
    raw = value.spec.to_dict()
    for group in raw["experiment"]["channel_controls"]:
        group["schedule"].append(dict(time=0.001, availability=0.0))
    branch = parse_spec(raw)
    changed = run(branch, branch_checkpoint(value.spec, checkpoint, branch))
    exact(tuple(v[0] for v in changed.history), checkpoint.state)
    np.testing.assert_array_equal(
        changed.history.channel_transferred[-1], checkpoint.state.channel_transferred
    )
    assert np.any(changed.history.channel_gate[-1] != checkpoint.state.channel_gate)
    raw["model"]["channels"][1]["kinetic_law"] = "betse_kv1p5_mh@1"
    with pytest.raises((ConfigError, ValueError)):
        branch_checkpoint(value.spec, checkpoint, parse_spec(raw))
    parts = list(iter_windows(value.spec, WindowPolicy(17, "full"), checkpoint))
    merged = tuple(
        np.concatenate([getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(parts)])
        for k in model.STATE_TYPE._fields
    )
    exact(merged, resumed.history)
    process = subprocess.run(
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
        capture_output=True,
        text=True,
        timeout=600,
    )
    (tmp_path / "fresh.stdout.log").write_text(process.stdout)
    (tmp_path / "fresh.stderr.log").write_text(process.stderr)
    process.check_returncode()
    exact(load_snapshot(tmp_path / "fresh/checkpoint_final").checkpoint.state, resumed.final.state)
    evidence(
        "restart",
        dict(
            status="passed",
            state_fields=list(model.STATE_TYPE._fields),
            comparison="bitwise",
            disk=True,
            fresh_process=True,
            terminal=True,
            future_branch=True,
            changed_windows=True,
            changed_law_rejected=True,
        ),
    )


def test_trajectory_batch_budget():
    specs = [parse_spec(fixtures.definition(arm)) for arm in ("clamped", "release")]
    batch = BatchSpec(
        tuple(WorldSpec(10 + i, s) for i, s in enumerate(specs)), 2, BATCH_STEP_BUDGET, 2**29
    )
    planned = plan_batch(batch)
    evidence(
        "batch-plan",
        dict(
            status="passed",
            inputs=batch.to_dict(),
            conservative_padded_steps=planned.padded_step_bound,
            budget=BATCH_STEP_BUDGET,
            scope="Host planning only; no trajectories",
        ),
    )


def test_worlds_ensemble_and_independent_restart(trajectories, tmp_path):
    expected = [trajectories[a] for a in ("clamped", "release")]
    batch = BatchSpec(
        tuple(WorldSpec(i + 10, v.spec) for i, v in enumerate(expected)),
        2,
        BATCH_STEP_BUDGET,
        2**29,
    )
    result = run_batch(batch)
    reordered = run_batch(BatchSpec(tuple(reversed(batch.worlds)), 2, BATCH_STEP_BUDGET, 2**29))
    for identity in (10, 11):
        exact(result.worlds[identity].history, expected[identity - 10].history)
        exact(reordered.worlds[identity].history, result.worlds[identity].history)
        single = run_batch(BatchSpec((batch.worlds[identity - 10],), 1, BATCH_STEP_BUDGET, 2**29))
        exact(single.worlds[identity].history, result.worlds[identity].history)
    checkpoints = result.checkpoint_at({10: 0.001, 11: 0.002})
    write_batch_snapshot(tmp_path / "batch", batch, checkpoints)
    loaded = load_batch_snapshot(tmp_path / "batch")
    parts = list(iter_batch_windows(loaded.spec, WindowPolicy(17, "full"), loaded.checkpoints))
    for identity in (10, 11):
        rows = [p.worlds[identity] for p in parts if identity in p.worlds]
        merged = tuple(
            np.concatenate(
                [getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(rows)]
            )
            for k in model.STATE_TYPE._fields
        )
        exact(
            merged,
            tuple(v[checkpoints[identity].step_index :] for v in result.worlds[identity].history),
        )
    ensemble = ionic.parse_spec(
        dict(
            model="ionic_worlds@1", simulation=expected[0].spec.to_dict(), worlds=1, window_steps=17
        )
    )
    checkpoints, report = ionic.run(ensemble, backend=BACKEND)
    exact(checkpoints[1].state, expected[0].final.state)
    assert report["final_voltage_axis"] == "membrane_patch"
    np.testing.assert_array_equal(
        report["final_voltage_V"][0], expected[0].observations.membrane_voltage_V[-1, :4]
    )
    evidence(
        "worlds",
        dict(
            status="passed",
            world_ids=[10, 11],
            reordered=True,
            partitioned=True,
            independent_restart_times=[0.001, 0.002],
            comparison="bitwise",
            ensemble_report=report,
        ),
    )


def test_cpu_gpu(trajectories):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU histories")
    assert EVIDENCE
    count = 0
    for arm, result in trajectories.items():
        actual = {
            **result.history._asdict(),
            **{"observed_" + k: v for k, v in vars(result.observations).items()},
        }
        with np.load(
            Path(EVIDENCE) / "cpu" / (PREFIX + "-trajectory-" + arm + ".npz"),
            allow_pickle=False,
        ) as saved:
            assert set(actual) == set(saved.files)
            for name, values in actual.items():
                atol = (
                    3e-25
                    if name.endswith("_C")
                    else 3e-23
                    if name.endswith("_A")
                    else 3e-11
                    if name.endswith("_V")
                    else 3e-13
                )
                np.testing.assert_allclose(values, saved[name], rtol=3e-10, atol=atol)
                count += values.size
    evidence("cpu-gpu", dict(status="passed", physical_scalars=count, histories=4, state_arrays=19))
